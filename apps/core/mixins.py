from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404


class OwnerRequiredMixin(LoginRequiredMixin):
    """Filter detail/edit views so they only resolve the requesting user's rows.

    Returns 404 (not 403) for foreign objects so that the URL space does not leak
    the existence of other users' resources.
    """

    owner_field = "owner"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(**{self.owner_field: self.request.user})

    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except self.model.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise Http404 from exc
