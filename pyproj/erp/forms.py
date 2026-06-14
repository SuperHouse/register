# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms

from .models import Batch, BatchProductionStage, ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


class ProductionStageForm(forms.ModelForm):
    class Meta:
        model = ProductionStage
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-color', 'type': 'color'}),
        }


class ProductionStageTemplateForm(forms.ModelForm):
    class Meta:
        model = ProductionStageTemplate
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProductionStageTemplateStepForm(forms.ModelForm):
    class Meta:
        model = ProductionStageTemplateStep
        fields = ['production_stage']
        widgets = {
            'production_stage': forms.Select(attrs={'class': 'form-select'}),
        }


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['design', 'reference', 'quantity', 'notes']
        widgets = {
            'design': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class BatchApplyTemplateForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=ProductionStageTemplate.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class BatchProductionStageAddForm(forms.Form):
    production_stage = forms.ModelChoiceField(
        queryset=ProductionStage.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class BatchProductionStageUpdateForm(forms.ModelForm):
    class Meta:
        model = BatchProductionStage
        fields = ['due_date', 'completion_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'completion_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'step': '1', 'class': 'form-control form-control-sm'},
                format='%Y-%m-%dT%H:%M:%S',
            ),
        }
