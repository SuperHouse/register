# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms

from device.models import Design
from .models import Batch, BatchProductionStage, Location, Part, PartAsset, PartCategory, ProductionStage, ProductionStageTemplate, ProductionStageTemplateStep


class DesignChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.client.company_name} {obj.sku}: {obj.name} {obj.hw_version}'


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
    design = DesignChoiceField(
        queryset=Design.objects.select_related('client').order_by(
            'client__company_name', 'sku', 'name', 'hw_version'
        ),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Batch
        fields = ['design', 'reference', 'quantity', 'notes']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class BatchApplyTemplateForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=ProductionStageTemplate.objects.order_by('order', 'name'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class BatchProductionStageAddForm(forms.Form):
    production_stage = forms.ModelChoiceField(
        queryset=ProductionStage.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['parent', 'name', 'description']
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        exclude_pk = kwargs.pop('exclude_pk', None)
        super().__init__(*args, **kwargs)
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = '(top level)'
        if exclude_pk:
            excluded = _get_descendant_pks(list(Location.objects.all()), exclude_pk) | {exclude_pk}
            self.fields['parent'].queryset = Location.objects.exclude(pk__in=excluded)


def _get_descendant_pks(all_locations, root_pk):
    """Return the set of PKs of all descendants of root_pk."""
    result = set()
    to_visit = [root_pk]
    while to_visit:
        current = to_visit.pop()
        for loc in all_locations:
            if loc.parent_id == current:
                result.add(loc.pk)
                to_visit.append(loc.pk)
    return result


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = ['name', 'description', 'category', 'device', 'package', 'value', 'fusion_library', 'image', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'device': forms.TextInput(attrs={'class': 'form-control'}),
            'package': forms.TextInput(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'fusion_library': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].empty_label = '(uncategorised)'


class PartAssetForm(forms.ModelForm):
    class Meta:
        model = PartAsset
        fields = ['file', 'name', 'description']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }


class PartCategoryForm(forms.ModelForm):
    class Meta:
        model = PartCategory
        fields = ['parent', 'name', 'description']
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        exclude_pk = kwargs.pop('exclude_pk', None)
        super().__init__(*args, **kwargs)
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = '(top level)'
        if exclude_pk:
            excluded = _get_descendant_pks(list(PartCategory.objects.all()), exclude_pk) | {exclude_pk}
            self.fields['parent'].queryset = PartCategory.objects.exclude(pk__in=excluded)


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
