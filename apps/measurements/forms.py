from django import forms

from .models import Measurement

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
VALID_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv")


class MeasurementUploadForm(forms.ModelForm):
    class Meta:
        model = Measurement
        fields = ["video", "captured_at", "scale_ref_m"]
        widgets = {
            "captured_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "video": forms.FileInput(attrs={
                "accept": "video/*",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["video"].required = True

    def clean_video(self):
        video = self.cleaned_data["video"]
        if video.size > MAX_UPLOAD_BYTES:
            mb = video.size / 1024 / 1024
            raise forms.ValidationError(
                f"파일이 너무 큽니다 ({mb:.1f} MB). 최대 200MB."
            )
        if not video.name.lower().endswith(VALID_EXTENSIONS):
            raise forms.ValidationError(
                f"지원 확장자: {', '.join(VALID_EXTENSIONS)}"
            )
        return video
