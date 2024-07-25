from datetime import date

from django import forms
from django.forms.widgets import HiddenInput

from .models import Design, Device, DeviceEvent, TestRecord


class DeviceEventForm(forms.ModelForm):
    class Meta:
        model = DeviceEvent
        fields = ['internal', 'description']


class TestRecordForm(forms.ModelForm):
    __test__ = False  # Stop PyTest from treating this model as a test class.

    class Meta:
        model = TestRecord
        exclude = ['device']

