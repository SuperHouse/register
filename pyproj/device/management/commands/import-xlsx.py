import datetime
import re
import string
import zoneinfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from openpyxl import load_workbook

from device.models import DeviceEvent, TestImage, TestRecord, Device, Design, Client, witching_hour, tz

timezone.activate(tz)


def int_map(i):
    try:
        return int(i)
    except TypeError:
        return None


def date_from_str(s):
    matchers = (
        '%d-%b-%Y',
        '%Y-%m-%d',
        '%d/%m/%Y',
    )
    for matcher in matchers:
        w = witching_hour
        try:
            # Make a timezone-aware datetime from a string and a timezone
            matched_date = timezone.datetime.strptime(s, matcher).date()
            dt = datetime.datetime.combine(matched_date, witching_hour, tzinfo=tz)

            return dt
        except ValueError:
            pass

    raise ValueError(f"oh dear, couldn't parse {s} as a date.")


class Command(BaseCommand):
    help = 'Import data from an XLSX file'
    output_transaction = True  # Put all db ops in a transaction

    def add_arguments(self, parser):
        # parser.add_argument('filename', nargs='?', help='XLSX file to import from')
        parser.add_argument('filename', help='XLSX file to import from')
        # parser.add_argument('dryrun', type=bool, help='Dry run (no db changes)')
        pass

    def handle(self, *args, **options):
        filename = options['filename']
        # filename = 'pyproj/stash/Device Serial Numbers-3.xlsx'
        self.stdout.write(f'Importing from {filename}')

        wb = load_workbook(filename=filename)

        known_sheets = 'Devices/Queue/DeviceTypes/Raw Serials/Patched Boards'
        assert set(known_sheets.split('/')) == set(
            wb.sheetnames
        ), f'Expected sheets: {known_sheets}; Actual sheets: {wb.sheetnames}'

        # Read from the second sheet, DeviceTypes
        ws_design = wb['DeviceTypes']

        known_design_keys = tuple('Serial/ClientSerial/SKU/Name/HW Version/Customer/Price/Price2'.split('/'))
        design_keys = tuple(cell.value for cell in ws_design['1'] if cell.value is not None)
        # self.stdout.write(f'{design_keys=}')
        assert design_keys == known_design_keys

        col_map = {key: letter for letter, key in zip(string.ascii_uppercase, known_design_keys)}
        # self.stdout.write(f'{col_map=}')

        client_serials = tuple(int_map(cell.value) for cell in ws_design[col_map["ClientSerial"]][1:])
        client_names = tuple(cell.value for cell in ws_design[col_map['Customer']][1:])
        client_info = zip(client_serials, client_names)
        client_map = {}
        for client_id, name in client_info:
            if name is None:
                continue
            # self.stdout.write(f'{client_id=} {name=}')
            if client_id in client_map:
                assert client_map[client_id] == name
            else:
                client_map[client_id] = name

        # self.stdout.write(f'{client_map}')

        # Delete all data except for clients (which we'll update)
        Device.objects.all().delete()
        Design.objects.all().delete()

        # Import / update clients
        for id, name in client_map.items():
            try:
                client = Client.objects.get(pk=id)
                # print(f'Name in SQL: {client.company_name}; Name in XLSX: {name}')
                # If we wanted to update client records in the db from the sheet, do it here.
            except Client.DoesNotExist:
                # New client
                client = Client(pk=id, company_name=name)
                client.save()

        # Import designs
        design_count = 0
        for row in ws_design.iter_rows(min_row=2, max_col=len(col_map.keys()), max_row=999):
            row = dict(zip(design_keys, (cell.value for cell in row)))
            # self.stdout.write(f'{row=}')
            if row['SKU'] is None:
                break
            id = int(row['Serial'])
            client_id = int(row['ClientSerial']) if row['ClientSerial'] else next_client_id
            design_data = {
                'id': id,
                'client_id': client_id,
                'sku': row['SKU'],
                'name': row['Name'],
                'hw_version': row['HW Version'],
            }
            if row['Price']:
                design_data['price'] = row['Price']
            if row['Price2']:
                design_data['price2'] = row['Price2']
            design = Design(**design_data)
            design.save()
            design_count += 1

        # Now read from the first sheet, Devices
        ws_device = wb['Devices']

        known_device_keys = tuple(
            'Serial/DeviceTypeSerial/Assembled/Tested/Firmware/Notes/Device/HW Version/Invoice/PO/Shipped'.split('/')
        )
        device_keys = tuple(cell.value for cell in ws_device['1'] if cell.value is not None)
        # self.stdout.write(f'{device_keys=}')
        assert device_keys == known_device_keys

        col_map = {key: letter for letter, key in zip(string.ascii_uppercase, known_device_keys)}
        # self.stdout.write(f'{col_map=}')

        # Import devices
        tr = []
        de_list = []
        tr_list = []
        device_count = 0
        for row in ws_device.iter_rows(min_row=2, max_col=len(col_map.keys()), max_row=9999):
            row = dict(zip(device_keys, (cell.value for cell in row)))
            if row['DeviceTypeSerial'] is None:
                continue
            # self.stdout.write(f'{row=}')
            device_id = int(row['Serial'])
            design_id = int(row['DeviceTypeSerial'])
            tested = row['Tested']
            sw_version = row['Firmware']
            creation_dt = row['Assembled']
            notes = row['Notes']
            invoice = row['Invoice']
            shipping = row['Shipped']
            porder = row['PO']

            if invoice:
                try:
                    # If the invoice is a straight number, it'll have .0 on the end.  Convert to string via int.
                    invoice = str(int(invoice))
                except ValueError:
                    # Just take the string, may not have been a straight number.
                    invoice = str(invoice)

            if porder:
                try:
                    # If the porder is a straight number, it'll have .0 on the end.  Convert to string via int.
                    porder = str(int(porder))
                except ValueError:
                    # Just take the string, may not have been a straight number.
                    porder = str(porder)

            if notes:
                dated_event_in_note_matchers = (
                    r'(\d{1,2}-[A-Z][a-z]{2}-202\d)',
                    r'(\d+/\d+/202\d)',
                )
                for matcher in dated_event_in_note_matchers:
                    match = re.search(matcher, notes)
                    if match:
                        # self.stdout.write(f'{row=}')
                        # self.stdout.write(f'{notes=}')
                        # d = match.groupdict()
                        # d_str = f'{d=}'
                        # self.stdout.write(d_str)
                        de_data = {
                            'device_id': device_id,
                            'event_dt': date_from_str(match.group()),
                            'event_type': 'NOTE',
                            'description': notes,
                        }
                        de_list.append(de_data)
                        notes = None
                        break

            if shipping:
                match = re.search(r'(\d{1,2}-[A-Z][a-z]{2}-202\d) (.*)', shipping)
                assert match
                # self.stdout.write(f'{row=}')
                # self.stdout.write(f'{shipping=}')
                # d = match.groupdict()
                # d_str = f'{d=}'
                # self.stdout.write(d_str)
                de_data = {
                    'device_id': device_id,
                    'event_dt': date_from_str(match.group(1)),
                    'event_type': 'SHIPPING',
                    'description': match.group(2),
                }
                de_list.append(de_data)

            if tested:
                assert type(tested) == datetime.datetime
                test_dt = datetime.datetime.combine(tested.date(), witching_hour, tzinfo=tz)
                tr_data = {
                    'device_id': device_id,
                    'test_dt': test_dt,
                    'result': TestRecord.PASS,
                    'notes': 'Test date imported from spreadsheet.',
                }
                tr_list.append(tr_data)

            if sw_version:
                de_data = {
                    'device_id': device_id,
                    'event_dt': timezone.now(),
                    'event_type': 'SW_VERSION',
                    'description': sw_version,
                }
                de_list.append(de_data)

            device_data = {
                'id': device_id,
                'design_id': design_id,
                'creation_dt': datetime.datetime.combine(creation_dt.date(), witching_hour, tzinfo=tz),
                'invoice': invoice,
                'po': porder,
                'notes': notes,
            }

            device = Device(**device_data)
            device.save()
            device_count += 1

        for de_data in de_list:
            de = DeviceEvent(**de_data)
            de.save()

        for tr_data in tr_list:
            tr = TestRecord(**tr_data)
            tr.save()

        self.stdout.write(f'Imported {design_count} designs, and {device_count} devices.')

        self.stdout.write(self.style.SUCCESS('Done.'))
