# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms

from device.models import Design
from .models import Tester, TestModule, TestModuleType


class DesignChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.client.company_name} {obj.sku}: {obj.name} v{obj.hw_version}'


class TesterForm(forms.ModelForm):
    class Meta:
        model = Tester
        fields = ['name', 'version', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class TestModuleTypeForm(forms.ModelForm):
    class Meta:
        model = TestModuleType
        fields = ['name', 'version']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TestModuleForm(forms.ModelForm):
    class Meta:
        model = TestModule
        fields = ['module_type', 'notes']
        widgets = {
            'module_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CompatibleDesignAddForm(forms.Form):
    design = DesignChoiceField(
        queryset=Design.objects.filter(obsolete=False).select_related('client').order_by(
            'client__company_name', 'sku', 'name', 'hw_version'
        ),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, module_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Designs already compatible with this module type aren't offered again.
        if module_type is not None:
            self.fields['design'].queryset = self.fields['design'].queryset.exclude(
                pk__in=module_type.compatible_designs.values_list('pk', flat=True)
            )
