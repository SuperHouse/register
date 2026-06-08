import re
from datetime import date, datetime

from django import forms
from django.forms.widgets import HiddenInput
from django.utils import timezone

from .models import Design, Device, DeviceAsset, DeviceEvent, DeviceImage, DesignAsset, TestRecord
from crm.models import Client


class DateTimeLocalInput(forms.DateTimeInput):
    """Custom widget for datetime-local input that formats values correctly."""
    input_type = 'datetime-local'
    format = '%Y-%m-%dT%H:%M'  # Format for datetime-local input
    
    def format_value(self, value):
        """Format datetime value for datetime-local input (YYYY-MM-DDTHH:MM)."""
        if value is None:
            return ''
        if isinstance(value, str):
            return value
        # Convert timezone-aware datetime to local timezone and format
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        # Format as YYYY-MM-DDTHH:MM (datetime-local format, no seconds)
        return value.strftime('%Y-%m-%dT%H:%M')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['company_name', 'logo', 'users', 'api_key']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'users': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '10'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'company_name': 'Company Name',
            'logo': 'Logo',
            'users': 'Users',
            'api_key': 'API Key',
        }
        help_texts = {
            'api_key': 'API key for authentication',
            'users': 'Hold Ctrl (Cmd on Mac) to select multiple users',
        }


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


class DeviceImageForm(forms.ModelForm):
    class Meta:
        model = DeviceImage
        fields = ['image', 'notes']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'image': 'Image File',
            'notes': 'Notes',
        }
        help_texts = {
            'image': 'Date/time will be extracted from filename if it matches pattern "id-YYYY-MM-DD_h-m-s", otherwise current time will be used',
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Extract date/time from filename or use current time
        uploaded_file = self.cleaned_data.get('image')
        filename_dt = None
        
        if uploaded_file:
            filename = uploaded_file.name
            # Extract just the filename without path (in case it has one)
            if '/' in filename or '\\' in filename:
                filename = filename.replace('\\', '/').split('/')[-1]
            # Remove file extension
            name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            # Pattern: id-YYYY-MM-DD_h_m_s (e.g., "123-2024-01-15_14-30-45")
            # The id part can be any characters before the first dash
            pattern = r'^.+?-(\d{4})-(\d{2})-(\d{2})_(\d{1,2})-(\d{1,2})-(\d{1,2})$'
            match = re.match(pattern, name_without_ext)
            
            if match:
                try:
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    hour = int(match.group(4))
                    minute = int(match.group(5))
                    second = int(match.group(6))
                    
                    # Validate the date/time values
                    if not (1 <= month <= 12 and 1 <= day <= 31 and 
                           0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                        raise ValueError("Invalid date/time values")
                    
                    # Create datetime object
                    parsed_dt = datetime(year, month, day, hour, minute, second)
                    # Make it timezone-aware using the current timezone
                    if timezone.is_naive(parsed_dt):
                        parsed_dt = timezone.make_aware(parsed_dt)
                    
                    filename_dt = parsed_dt
                except (ValueError, TypeError):
                    # If parsing fails, filename_dt remains None
                    pass
        
        # Set image_dt: use filename datetime if found, otherwise current time
        if filename_dt:
            instance.image_dt = filename_dt
        else:
            instance.image_dt = timezone.now()
        
        if commit:
            instance.save()
        return instance


class DesignAssetForm(forms.ModelForm):
    class Meta:
        model = DesignAsset
        fields = ['file', 'name', 'description', 'asset_type', 'internal']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'asset_type': forms.Select(attrs={'class': 'form-select'}),
            'internal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DesignAssetEditForm(forms.ModelForm):
    class Meta:
        model = DesignAsset
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DeviceAssetForm(forms.ModelForm):
    class Meta:
        model = DeviceAsset
        fields = ['file', 'name', 'description', 'asset_type', 'internal']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'asset_type': forms.Select(attrs={'class': 'form-select'}),
            'internal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DeviceAssetEditForm(forms.ModelForm):
    class Meta:
        model = DeviceAsset
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DeviceImageEditForm(forms.ModelForm):
    """Form for editing device image notes only."""
    class Meta:
        model = DeviceImage
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'notes': 'Notes',
        }

