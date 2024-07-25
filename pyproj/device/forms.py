from datetime import date

from django import forms
from django.forms.widgets import HiddenInput

from .models import Design, Device, DeviceEvent, TestRecord


class DeviceEventForm(forms.ModelForm):
    class Meta:
        model = DeviceEvent
        fields = ['event_dt', 'event_type', 'internal', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Disable the event type if the event already exists.
            self.fields['event_type'].disabled = True


class TestRecordForm(forms.ModelForm):
    __test__ = False  # Stop PyTest from treating this model as a test class.

    class Meta:
        model = TestRecord
        exclude = ['device']

