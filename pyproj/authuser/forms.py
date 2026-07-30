from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, _unicode_ci_compare

User = get_user_model()


class InvitePasswordResetForm(PasswordResetForm):
    """PasswordResetForm, but also targets accounts with no usable password yet.

    Django's own get_users() deliberately excludes users where
    has_usable_password() is False, to stop a "reset" being sent for an
    account that never had a real password (e.g. SSO-only). That's exactly
    the state a newly invited user is in (see crm.views.users.user_add),
    so the stock form would silently email nobody for every invite.
    """

    def get_users(self, email):
        email_field_name = User.get_email_field_name()
        active_users = User._default_manager.filter(**{
            f'{email_field_name}__iexact': email,
            'is_active': True,
        })
        return (
            u for u in active_users
            if _unicode_ci_compare(email, getattr(u, email_field_name))
        )


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

