from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from crm.forms import UserForm

User = get_user_model()


def _send_set_password_email(request, user):
    reset_form = PasswordResetForm(data={'email': user.email})
    if reset_form.is_valid():
        reset_form.save(
            request=request,
            use_https=request.is_secure(),
            from_email='noreply@superhouse.tv',
            email_template_name='registration/superhouse_password_reset_email.html',
            subject_template_name='registration/superhouse_password_reset_subject.txt',
        )


@staff_member_required
def user_list(request):
    """List all users."""
    users = User.objects.all().order_by('full_name', 'email')

    q = request.GET.get('q', '').strip()
    if q:
        users = users.filter(Q(full_name__icontains=q) | Q(email__icontains=q))

    paginator = Paginator(users, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'q': q,
    }

    return render(request, 'device/user_list.html', context)


@staff_member_required
def user_add(request):
    """Add a new user."""
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_unusable_password()
            user.save()
            form.save_m2m()
            _send_set_password_email(request, user)
            messages.success(request, 'User added successfully. They have been emailed a link to set their password.')
            return redirect('user_edit', user_id=user.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors. Please review, and amend as required.",
            )
    else:
        form = UserForm()

    context = {
        'form': form,
    }

    return render(request, 'device/user_edit.html', context)


@staff_member_required
def user_edit(request, user_id):
    """Edit a user, including their org memberships and API key."""
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User updated successfully.')
            return redirect('user_edit', user_id=user.pk)
        else:
            messages.warning(
                request,
                "Some field values have errors. Please review, and amend as required.",
            )
    else:
        form = UserForm(instance=user)

    context = {
        'form': form,
        'user_obj': user,
    }

    return render(request, 'device/user_edit.html', context)


@staff_member_required
@require_POST
def user_regenerate_key(request, user_id):
    """Regenerate a user's API key."""
    user = get_object_or_404(User, pk=user_id)
    user.regenerate_api_key()
    messages.success(request, "User's API key has been regenerated.")

    return redirect('user_edit', user_id=user.pk)
