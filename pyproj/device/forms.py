from datetime import date

from django import forms
from django.forms.widgets import HiddenInput

from .models import Design, Device, DeviceEvent
from .models import Design, Device


class AddDevicesForm(forms.Form):
    # This allows us to override warnings on serial number and assembly date not matching expected.
    # This field is hidden on first page rendering.  Must come before the two fields with clean
    # methods, or else the value of override_warnings will be None when the clean methods are called.
    override_warnings = forms.BooleanField(label='Override warnings?', required=False)

    # FIXME: Separate design into board and hw version.  Do a two-dropdown form.
    design = forms.ModelChoiceField(
        label='Design', empty_label="Select a design...", queryset=Design.objects.order_by("name", "hw_version")
    )
    qty = forms.IntegerField(label='Number of new devices', min_value=1, max_value=1000)
    first_serial = forms.IntegerField(label='First serial number')
    assembly_date = forms.DateField(label='Assembly date', required=False)

    def __init__(self, *args, **kwargs):
        hide_override = kwargs.pop('hide_override', False)
        super().__init__(*args, **kwargs)
        if hide_override:
            self.fields['override_warnings'].widget = HiddenInput()

    @staticmethod
    def get_initials():
        initial = {
            'qty': 1,
            'first_serial': Device.first_free_serial(),
            'assembly_date': date.today(),
            'override_warnings': False,
        }

        return initial

    def clean_first_serial(self):
        override_warnings = self.cleaned_data.get('override_warnings', False)
        first_free_serial_from_form = self.cleaned_data['first_serial']
        first_free_serial_from_db = Device.first_free_serial()
        if not override_warnings and first_free_serial_from_form != first_free_serial_from_db:
            raise forms.ValidationError("Requested serial number isn't first available")

        return first_free_serial_from_form

    def clean_assembly_date(self):
        override_warnings = self.cleaned_data.get('override_warnings', False)
        assembly_date = self.cleaned_data['assembly_date']
        if not override_warnings and assembly_date != date.today():
            raise forms.ValidationError("Requested assembly date isn't today")

        return assembly_date


class DeviceEventForm(forms.ModelForm):
    class Meta:
        model = DeviceEvent
        fields = ['internal', 'event_type', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set help text for event_type field.  For some reason, this help text doesn't render.
        self.fields['event_type'].help_text = 'Recognised: "NOTE", "SHIP", "INV"'
