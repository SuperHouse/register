# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms
from django.db.models import Q

from device.models import Design
from .models import (
    Batch, BatchProductionStage, BomEquivalenceRule, BomExclusionRule, BomLibrarySetting, DesignBomEntry, Location,
    Part, PartAsset, PartCategory, PartSubstitution, ProductionStage, ProductionStageTemplate,
    ProductionStageTemplateStep,
)


class DesignChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.client.company_name} {obj.sku}: {obj.name} v{obj.hw_version}'


class GroupedPartChoiceIterator(forms.models.ModelChoiceIterator):
    """Yields Part options grouped into <optgroup>s by category name
    (uncategorised parts last), matching the PartReparentForm dropdown."""

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ('', self.field.empty_label)

        groups = {}
        uncategorised = []
        for part in self.queryset:
            choice = self.choice(part)
            if part.category_id:
                groups.setdefault(part.category.name, []).append(choice)
            else:
                uncategorised.append(choice)

        for cat_name in sorted(groups):
            yield (cat_name, groups[cat_name])
        if uncategorised:
            yield ('(uncategorised)', uncategorised)


class GroupedPartChoiceField(forms.ModelChoiceField):
    """A ModelChoiceField over Part whose options are grouped into
    <optgroup>s by category. Set the queryset with
    ``select_related('category').order_by('category__name', 'name')`` so
    grouping and per-group ordering are correct without extra queries."""

    iterator = GroupedPartChoiceIterator


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
        queryset=Design.objects.filter(obsolete=False).select_related('client').order_by(
            'client__company_name', 'sku', 'name', 'hw_version'
        ),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Batch
        fields = ['design', 'po', 'quantity', 'notes']
        widgets = {
            'po': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # An existing batch may be tied to a design that has since been
        # marked obsolete; keep it selectable so editing doesn't fail
        # validation or silently drop the field, without offering other
        # obsolete designs as new choices.
        if self.instance.pk and self.instance.design_id:
            self.fields['design'].queryset = Design.objects.filter(
                Q(obsolete=False) | Q(pk=self.instance.design_id)
            ).select_related('client').order_by('client__company_name', 'sku', 'name', 'hw_version')


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
        fields = [
            'name', 'description', 'category', 'device', 'package', 'value', 'smt_joints', 'pth_joints',
            'fusion_library', 'stock', 'no_stock_required', 'image',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'device': forms.TextInput(attrs={'class': 'form-control'}),
            'package': forms.TextInput(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'smt_joints': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'pth_joints': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'fusion_library': forms.TextInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'no_stock_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': PartImageWidget(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].empty_label = '(uncategorised)'


class PartSourceForm(forms.Form):
    """Spans both PartSource (listing) and PartSourceVariant (variant) tiers.

    The view get-or-creates the listing by (part, supplier_name, manufacturer_sku) and
    always creates a new variant for the supplier_sku/packaging/url, so adding a second
    SKU for a manufacturer_sku that's already on file groups it under the same listing
    (and shares its stock) instead of creating a duplicate listing.
    """
    supplier_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    supplier_sku = forms.CharField(
        max_length=200, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    url = forms.URLField(required=False, widget=forms.URLInput(attrs={'class': 'form-control'}))
    manufacturer_sku = forms.CharField(
        max_length=200, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    packaging = forms.CharField(
        max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    moq = forms.IntegerField(
        required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
    )
    stock = forms.IntegerField(
        required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
    )


class PartSubstitutionForm(forms.ModelForm):
    substitute = GroupedPartChoiceField(
        queryset=Part.objects.none(),
        empty_label='— select a part —',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    class Meta:
        model = PartSubstitution
        fields = ['substitute']

    def __init__(self, *args, exclude_pk=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Part.objects.select_related('category').order_by('category__name', 'name')
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        self.fields['substitute'].queryset = qs


class PartReparentForm(forms.Form):
    target_part = forms.ChoiceField(
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        label='Target part',
    )

    def __init__(self, *args, exclude_pk=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = (
            Part.objects
            .filter(category__isnull=False)
            .select_related('category')
            .order_by('category__name', 'name')
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

        groups = {}
        for part in qs:
            groups.setdefault(part.category.name, []).append((part.pk, str(part)))

        choices = [('', '— select target part —')]
        for cat_name in sorted(groups):
            choices.append((cat_name, groups[cat_name]))
        self.fields['target_part'].choices = choices

    def clean_target_part(self):
        pk = self.cleaned_data.get('target_part')
        if not pk:
            raise forms.ValidationError('Please select a part.')
        try:
            return Part.objects.get(pk=int(pk))
        except (ValueError, Part.DoesNotExist):
            raise forms.ValidationError('Invalid part selected.')


class DesignBomEntryForm(forms.ModelForm):
    part = GroupedPartChoiceField(
        queryset=Part.objects.select_related('category').order_by('category__name', 'name'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    class Meta:
        model = DesignBomEntry
        fields = ['reference', 'part']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }


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
