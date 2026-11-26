from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Profile


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    error = None
    entered_ism = ''

    if request.method == 'POST':
        entered_ism = request.POST.get('ism', '').strip()
        parol = request.POST.get('parol', '')

        if not entered_ism or not parol:
            error = "Iltimos, ism (login) va parolni kiriting."
        else:
            user = authenticate(request, username=entered_ism, password=parol)
            if user is None:
                matched_user = User.objects.filter(username__iexact=entered_ism).first()
                if matched_user is not None:
                    user = authenticate(request, username=matched_user.username, password=parol)

            if user is not None:
                Profile.objects.get_or_create(
                    user=user,
                    defaults={
                        'ism': user.first_name or user.username,
                        'familiya': user.last_name or '',
                    },
                )
                login(request, user)
                request.session['show_welcome_splash'] = True
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect('home')
            else:
                error = "Login (ism) yoki parol noto'g'ri!"

    return render(request, 'acaunts/login.html', {
        'error': error,
        'entered_ism': entered_ism,
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    error = None
    entered_ism = ''

    if request.method == 'POST':
        entered_ism = request.POST.get('ism', '').strip()
        parol1 = request.POST.get('parol1', '')
        parol2 = request.POST.get('parol2', '')

        if not entered_ism:
            error = "Iltimos, ismingizni kiriting."
        elif not parol1:
            error = "Iltimos, parol kiriting."
        elif parol1 != parol2:
            error = "Kiritilgan parollar bir-biriga mos emas!"
        elif User.objects.filter(username__iexact=entered_ism).exists():
            error = "Bu ism allaqachon ro'yxatdan o'tgan. Boshqa ism kiriting."
        else:
            user = User.objects.create_user(
                username=entered_ism,
                password=parol1,
                first_name=entered_ism,
            )
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.ism = entered_ism
            profile.save()

            messages.success(request, "Tabriklaymiz! Ro'yxatdan muvaffaqiyatli o'tdingiz. Endi tizimga kiring.")
            return redirect('login')

    return render(request, 'acaunts/register.html', {
        'error': error,
        'entered_ism': entered_ism,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            'ism': request.user.first_name or request.user.username,
            'familiya': request.user.last_name or '',
        },
    )

    if request.method == 'POST':
        ism = request.POST.get('ism', '').strip()
        familiya = request.POST.get('familiya', '').strip()
        telefon = request.POST.get('telefon', '').strip()
        avatar = request.FILES.get('avatar')
        remove_avatar = request.POST.get('remove_avatar') == '1'

        if not ism:
            messages.error(request, "Ism maydoni bo'sh bo'lishi mumkin emas.")
        else:
            profile.ism = ism
            profile.familiya = familiya
            profile.telefon = telefon
            if remove_avatar:
                if profile.avatar:
                    profile.avatar.delete(save=False)
                profile.avatar = None
            elif avatar:
                profile.avatar = avatar
            profile.save()

            request.user.first_name = ism
            request.user.last_name = familiya
            request.user.save(update_fields=['first_name', 'last_name'])

            messages.success(request, "Profil ma'lumotlari muvaffaqiyatli saqlandi!")
            return redirect('profile')

    return render(request, 'acaunts/profile.html', {
        'profile': profile,
    })
