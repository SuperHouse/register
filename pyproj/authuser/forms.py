from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSettingsForm(forms.ModelForm):
    avatar_type = forms.ChoiceField(
        choices=User.AVATAR_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Profile Picture',
        help_text='Choose how your profile picture is displayed',
        required=True
    )
    
    class Meta:
        model = User
        fields = ['email', 'full_name', 'preferred_name', 'avatar_type']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'preferred_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'email': 'Email Address',
            'full_name': 'Full Name',
            'preferred_name': 'Preferred Name',
        }
        help_texts = {
            'email': 'Your email address is used for login.',
            'full_name': 'Your full name (e.g., Robert Menzies)',
            'preferred_name': 'Your preferred name or nickname (e.g., Bob)',
        }

