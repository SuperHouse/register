# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms

from .models import Operation, OperationTemplate, OperationTemplateStep


class OperationForm(forms.ModelForm):
    class Meta:
        model = Operation
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }


class OperationTemplateForm(forms.ModelForm):
    class Meta:
        model = OperationTemplate
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class OperationTemplateStepForm(forms.ModelForm):
    class Meta:
        model = OperationTemplateStep
        fields = ['operation']
        widgets = {
            'operation': forms.Select(attrs={'class': 'form-select'}),
        }
