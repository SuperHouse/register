import datetime
import re
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

    def handle(self, *args, **options):
        filename = options['filename']
        # filename = 'pyproj/stash/Device Serial Numbers.xlsx'
        self.stdout.write(f'Importing from {filename}')

        wb = load_workbook(filename=filename)

        known_sheets = 'Devices/DeviceTypes/Patched Boards/Serials/Solarcam Devices/T-Rex Devices/Raw Serials'
        assert set(known_sheets.split('/')) == set(wb.sheetnames), f'Expected sheets: {known_sheets}'

        # Read from the second sheet, DeviceTypes
        ws_design = wb['DeviceTypes']

        known_design_keys = tuple('Serial/ClientSerial/SKU/Name/HW Version/Customer/Price/Price2'.split('/'))
        design_keys = tuple(cell.value for cell in ws_design['1'] if cell.value is not None)
        # self.stdout.write(f'{design_keys=}')
        assert design_keys == known_design_keys

        col_map = {key: letter for letter, key in zip('ABCDEFGH', known_design_keys)}
        # self.stdout.write(f'{col_map=}')

        client_serials = tuple(int_map(cell.value) for cell in ws_design[col_map["ClientSerial"]][1:])
        client_names = tuple(cell.value for cell in ws_design[col_map['Customer']][1:])
        client_info = zip(client_serials, client_names)
        client_map = {}
        for client_id, name in client_info:
            if name is None:
                continue
            # self.stdout.write(f'{serial=} {name=}')
            if client_id in client_map:
                assert client_map[client_id] == name
            else:
                client_map[client_id] = name

        # Fix Bubblepay, which doesn't have an id in the XLSX
        # Is there any client with an id of None?
        if None in client_map:
            # Assign next id to Bubblepay
            next_client_id = max(v for v in client_map.keys() if v) + 1
            client_map[next_client_id] = client_map[None]
            del client_map[None]

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

        # Now read from the first sheet, Devices
        ws_device = wb['Devices']

        known_device_keys = tuple(
            'Serial/DeviceTypeSerial/Assembled/Tested/Firmware/Notes/Device/HW Version/Invoice'.split('/')
        )
        device_keys = tuple(cell.value for cell in ws_device['1'] if cell.value is not None)
        # self.stdout.write(f'{device_keys=}')
        assert device_keys == known_device_keys

        col_map = {key: letter for letter, key in zip('ABCDEFGHI', known_device_keys)}
        # self.stdout.write(f'{col_map=}')

        # Import devices
        tr = []
        de_list = []
        tr_list = []
        unmatched_notes = []
        for row in ws_device.iter_rows(min_row=2, max_col=len(col_map.keys()), max_row=9999):
            row = dict(zip(device_keys, (cell.value for cell in row)))
            if row['DeviceTypeSerial'] is None:
                continue
            # self.stdout.write(f'{row=}')
            device_id = int(row['Serial'])
            design_id = int(row['DeviceTypeSerial'])
            notes = row['Notes']
            assembly_date = row['Assembled']
            invoice_from_column = row['Invoice'] or ''
            if invoice_from_column:
                try:
                    # If the invoice is a straight number, it'll have .0 on the end.  Convert to string via int.
                    invoice_from_column = str(int(row['Invoice']))
                except ValueError:
                    # Just take the string, may not have been a straight number.
                    invoice_from_column = str(row['Invoice'])

            # FIXME: Take this code out when running on new spreadsheet
            known_no_assembly_dates = [
                {
                    'start_id': 1204,
                    'end_id': 1212,
                    'assembly_date': '2023-09-14',
                },
                {
                    'start_id': 1327,
                    'end_id': 1334,
                    'assembly_date': '2023-10-10',
                },
            ]

            for k in known_no_assembly_dates:
                if k['start_id'] <= device_id <= k['end_id']:
                    assembly_date = k['assembly_date']
                    notes = f'GUESSED ASSEMBLY DATE.  {notes}'

            if notes:
                destination_matchers = (
                    r'(?P<action>(Sent to|Set to|Collected by) ?)(?P<client>.+?) (?P<date>[^ ]+202\d?)',
                    r'(?P<action>(Sent to|Set to|Collected by) ?)(?P<client>.+?) (?P<date>2024-[0-9-]+)',
                    r'(?P<action>(Collected|Posted to Simon) ?)(?P<client>) (?P<date>[^ ]+202\d?)',
                )
                for matcher in destination_matchers:
                    match = re.search(matcher, notes)
                    if match:
                        # self.stdout.write(f'{row=}')
                        # self.stdout.write(f'{notes=}')
                        # d = match.groupdict()
                        # d_str = f'{d=}'
                        # self.stdout.write(d_str)
                        client = match['client'] or ''
                        de_data = {
                            'device_id': device_id,
                            'event_dt': date_from_str(match['date']),
                            'event_type': 'SHIP',
                            'description': f'{match["action"]}{client}',
                        }
                        de_list.append(de_data)

                        head_pos, tail_pos = match.span()
                        head = notes[0:head_pos].strip()
                        tail = notes[tail_pos:].strip()
                        notes = ' '.join((head, tail)).strip()
                        # print(f'{notes=} {de_data}')
                        break

                postage_matchers = (
                    r'(?P<agent>AusPost|TNT|Express Post) (?P<date>[^ ]+202\d?)(?P<connum> \w+[.]?)?',  # Agent date connum
                    r'(?P<agent>AusPost|TNT|Express Post)(?P<connum> \w+)? (?P<date>[^ ]+202\d?)',  # Agent connum date
                )

                for matcher in postage_matchers:
                    match = re.search(matcher, notes)
                    if match:
                        # self.stdout.write(f'{row=}')
                        # self.stdout.write(f'{notes=}')
                        # d = match.groupdict()
                        # d_str = f'{d=}'
                        # self.stdout.write(d_str)
                        connum = match['connum'] or ''
                        de_data = {
                            'device_id': device_id,
                            'event_dt': date_from_str(match['date']),
                            'event_type': 'SHIP',
                            'description': f'{match["agent"]}{connum}',
                        }
                        de_list.append(de_data)
                        head_pos, tail_pos = match.span()
                        head = notes[0:head_pos].strip()
                        tail = notes[tail_pos:].strip()
                        notes = ' '.join((head, tail)).strip()
                        # print(f'{notes=} {de_data}')
                        break

                invoice_matchers = (r'[Ii]nvoice (?P<invoice>\d+[.])',)
                for matcher in invoice_matchers:
                    match = re.search(matcher, notes)
                    if match:
                        # self.stdout.write(f'{row=}')
                        # self.stdout.write(f'{notes=}')
                        # d = match.groupdict()
                        # d_str = f'{d=}'
                        # self.stdout.write(d_str)
                        invoice_from_note = match['invoice'].strip()
                        if invoice_from_note.endswith('.'):
                            invoice_from_note = invoice_from_note[:-1]
                        if invoice_from_column:
                            assert invoice_from_note == invoice_from_column
                        else:
                            invoice_from_column = invoice_from_note
                        head_pos, tail_pos = match.span()
                        head = notes[0:head_pos].strip()
                        tail = notes[tail_pos:].strip()
                        notes = ' '.join((head, tail)).strip()
                        break

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
                            'description': f'<See device note for dated event, probably on this date>',
                        }
                        de_list.append(de_data)
                        break

            known_notes_matchers = (r'^Melted connector', r'^Missing valve', r'^Direct mounted', r'^Old accel')
            if notes:
                notes = notes.strip()
            if notes:
                if not any(re.search(matcher, notes) for matcher in known_notes_matchers):
                    if notes not in unmatched_notes:
                        unmatched_notes.append(notes)

            device_data = {
                'id': device_id,
                'design_id': design_id,
                'assembly_date': assembly_date,
                'sw_version': row['Firmware'],
                'invoice': invoice_from_column,
                'notes': notes,
            }

            test_dt = row['Tested']
            if test_dt:
                assert type(test_dt) == datetime.datetime
                test_dt = datetime.datetime.combine(test_dt.date(), witching_hour, tzinfo=tz)
                tr_data = {
                    'device_id': device_id,
                    'test_dt': test_dt,
                    'result': TestRecord.PASS,
                    'notes': 'Test date imported from spreadsheet.',
                }
                tr_list.append(tr_data)

            device = Device(**device_data)
            device.save()

        for de_data in de_list:
            de = DeviceEvent(**de_data)
            de.save()

        for tr_data in tr_list:
            tr = TestRecord(**tr_data)
            tr.save()

        self.stdout.write(f'Unmatched notes:')
        for u in unmatched_notes:
            self.stdout.write(f'  {u}')
        self.stdout.write(f'{len(unmatched_notes)} unmatched notes (which is ok)')

        self.stdout.write(self.style.SUCCESS('Done.'))
