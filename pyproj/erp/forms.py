# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms

from .models import ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


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
