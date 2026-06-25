from django import forms
from django.contrib.auth import get_user_model

from crm.models import Org

User = get_user_model()


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
