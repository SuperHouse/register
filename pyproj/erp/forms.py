# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms

from device.models import Design
from .models import (
    Batch, BatchProductionStage, BomEquivalenceRule, BomExclusionRule, BomLibrarySetting, Location, Part,
    PartAsset, PartCategory, PartSource, PartSubstitution, ProductionStage, ProductionStageTemplate,
    ProductionStageTemplateStep,
)


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


class PartImageWidget(forms.ClearableFileInput):
    """ClearableFileInput that omits "Currently" and shows only the bare filename."""
    initial_text = ''

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if context['widget'].get('is_initial') and hasattr(value, 'name'):
            from pathlib import Path
            _url = value.url
            _filename = Path(value.name).name

            class _FileProxy:
                url = _url
                def __str__(self_):
                    return _filename

            context['widget']['value'] = _FileProxy()
        return context


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = ['name', 'description', 'category', 'device', 'package', 'value', 'fusion_library', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'device': forms.TextInput(attrs={'class': 'form-control'}),
            'package': forms.TextInput(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'fusion_library': forms.TextInput(attrs={'class': 'form-control'}),
            'image': PartImageWidget(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].empty_label = '(uncategorised)'


class PartSourceForm(forms.ModelForm):
    class Meta:
        model = PartSource
        fields = ['supplier_name', 'supplier_sku', 'url', 'manufacturer_sku', 'packaging', 'stock']
        widgets = {
            'supplier_name': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier_sku': forms.TextInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'manufacturer_sku': forms.TextInput(attrs={'class': 'form-control'}),
            'packaging': forms.TextInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class PartSubstitutionForm(forms.ModelForm):
    class Meta:
        model = PartSubstitution
        fields = ['substitute']
        widgets = {
            'substitute': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }

    def __init__(self, *args, exclude_pk=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Part.objects.all()
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        self.fields['substitute'].queryset = qs
        self.fields['substitute'].empty_label = '— select a part —'


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


class BomLibrarySettingForm(forms.ModelForm):
    class Meta:
        model = BomLibrarySetting
        fields = ['library', 'ignore_device', 'ignore_package', 'ignore_value']
        widgets = {
            'library': forms.TextInput(attrs={'class': 'form-control'}),
            'ignore_device': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ignore_package': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ignore_value': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BomExclusionRuleForm(forms.ModelForm):
    class Meta:
        model = BomExclusionRule
        fields = ['library', 'device', 'package', 'value']
        widgets = {
            'library': forms.TextInput(attrs={'class': 'form-control'}),
            'device': forms.TextInput(attrs={'class': 'form-control'}),
            'package': forms.TextInput(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get('library') or cleaned_data.get('device')
                or cleaned_data.get('package') or cleaned_data.get('value')):
            raise forms.ValidationError('At least one of Library, Device, Package, or Value must be set.')
        return cleaned_data


class BomEquivalenceRuleForm(forms.ModelForm):
    class Meta:
        model = BomEquivalenceRule
        fields = [
            'from_library', 'to_library', 'from_device', 'to_device',
            'from_package', 'to_package', 'from_value', 'to_value',
        ]
        widgets = {
            'from_library': forms.TextInput(attrs={'class': 'form-control'}),
            'to_library': forms.TextInput(attrs={'class': 'form-control'}),
            'from_device': forms.TextInput(attrs={'class': 'form-control'}),
            'to_device': forms.TextInput(attrs={'class': 'form-control'}),
            'from_package': forms.TextInput(attrs={'class': 'form-control'}),
            'to_package': forms.TextInput(attrs={'class': 'form-control'}),
            'from_value': forms.TextInput(attrs={'class': 'form-control'}),
            'to_value': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data.get('from_library') or cleaned_data.get('from_device')
                or cleaned_data.get('from_package') or cleaned_data.get('from_value')):
            raise forms.ValidationError('At least one of From Library, From Device, From Package, or From Value must be set.')
        if not (cleaned_data.get('to_library') or cleaned_data.get('to_device')
                or cleaned_data.get('to_package') or cleaned_data.get('to_value')):
            raise forms.ValidationError('At least one of To Library, To Device, To Package, or To Value must be set.')
        return cleaned_data


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
