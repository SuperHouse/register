from django import forms
from django.contrib.auth import get_user_model

from crm.models import BrandedHost, Org

User = get_user_model()


class BrandedHostForm(forms.ModelForm):
    class Meta:
        model = BrandedHost
        fields = ['hostname', 'display_name', 'logo', 'logo_link_url', 'sidebar_colour', 'accent_colour']
        widgets = {
            'hostname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'serials.example.com'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'logo_link_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.example.com/'}),
            'sidebar_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#3c4b64'}),
            'accent_colour': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '#321fdb'}),
        }
        labels = {'logo_link_url': 'Logo link'}

    def clean_hostname(self):
        return self.cleaned_data['hostname'].strip().lower()

    def clean_sidebar_colour(self):
        return self.cleaned_data['sidebar_colour'].lower()

    def clean_accent_colour(self):
        return self.cleaned_data['accent_colour'].lower()


class UserForm(forms.ModelForm):
    orgs = forms.ModelMultipleChoiceField(
        queryset=Org.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': '10'}),
        label='Organisations',
        help_text='Hold Ctrl (Cmd on Mac) to select multiple organisations',
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'preferred_name', 'is_staff', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'preferred_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'email': 'Email Address',
            'full_name': 'Full Name',
            'preferred_name': 'Preferred Name',
            'is_staff': 'Staff',
            'is_active': 'Active',
        }
        help_texts = {
            'is_staff': 'Staff users can access all organisations and management pages.',
            'is_active': 'Unchecking this disables the account and its API key.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['orgs'].initial = self.instance.org_set.all()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.org_set.set(self.cleaned_data['orgs'])
        else:
            self.save_m2m = lambda: user.org_set.set(self.cleaned_data['orgs'])
        return user
