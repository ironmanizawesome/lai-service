from django import forms

from .models import CropProject


class CropProjectForm(forms.ModelForm):
    class Meta:
        model = CropProject
        fields = ["name", "crop_type", "species", "planted_at", "notes"]
        widgets = {
            "planted_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
