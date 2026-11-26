# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django import forms

from crm.models import Org
from device.models import Design

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['org', 'name', 'description', 'phase', 'status', 'start_date', 'target_date']
        widgets = {
            'org': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'phase': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'target_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Client orgs only, but keep the current org selectable if it has since stopped being one.
        orgs = Org.get_clients()
        if self.instance.pk:
            orgs = orgs | Org.objects.filter(pk=self.instance.org_id)
        self.fields['org'].queryset = orgs.distinct().order_by('company_name')

    def clean(self):
        cleaned = super().clean()
        start, target = cleaned.get('start_date'), cleaned.get('target_date')
        if start and target and target < start:
            self.add_error('target_date', 'The target date cannot be before the start date.')
        org = cleaned.get('org')
        if self.instance.pk and org and org.pk != self.instance.org_id:
            # Linked designs must belong to the project's org, or the client would see
            # another org's designs on their project page.
            if self.instance.designs.exclude(client=org).exists():
                self.add_error('org', 'Unlink the designs that belong to the current organisation first.')
        return cleaned


class ProjectDesignLinkForm(forms.Form):
    """Choose a design of the project's own org to link to the project."""

    design = forms.ModelChoiceField(queryset=None, widget=forms.Select(attrs={'class': 'form-select'}))

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['design'].queryset = (
            Design.objects.filter(client=project.org)
            .exclude(pk__in=project.designs.values('pk'))
            .order_by('obsolete', 'sku', 'hw_version')
        )
        self.fields['design'].empty_label = 'Choose a design…'
