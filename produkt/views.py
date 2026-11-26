import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from acaunts.models import Profile
from catigoriya.models import Catigoriya
from .models import (
    Buyurtma,
    BuyurtmaItem,
    Murojaat,
    Produkt,
    ProduktIzoh,
    SavatchaItem,
    Sevimli,
    calculate_yandex_estimate,
    format_uzs,
)


def _get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={
            'ism': user.first_name or user.username,
            'familiya': user.last_name or '',
        },
    )
    return profile


def _is_site_admin(user):
    return user.is_authenticated and user.username.lower() == 'tuzlama.uz'


def _serialize_user_cart(user):
    entries = (
        SavatchaItem.objects.filter(user=user)
        .select_related('produkt')
        .order_by('id')
    )
    items = []
    total_count = 0
    total_amount = Decimal('0')
    for entry in entries:
        p = entry.produkt
        if entry.quantity <= 0:
            continue
        total_count += entry.quantity
        total_amount += Decimal(str(p.narx)) * entry.quantity
        items.append({
            'id': p.id,
            'name': p.nom,
            'price': float(p.narx),
            'formatted_price': p.formatted_narx,
            'img': p.rasm.url if p.rasm else '',
            'quantity': entry.quantity,
        })
    return {
        'items': items,
        'total_count': total_count,
        'total_amount': float(total_amount),
        'formatted_total': format_uzs(total_amount),
    }


@login_required
def home_view(request):
    profile = _get_or_create_profile(request.user)
    show_splash = request.session.pop('show_welcome_splash', False)

    categories = Catigoriya.objects.annotate(product_count=Count('produktlar'))
    products = (
        Produkt.objects.select_related('catigoriya')
        .annotate(avg_rating=Avg('izohlar__rating'), review_count=Count('izohlar', distinct=True))
        .all()
    )

    selected_category = request.GET.get('cat', '')
    search_query = request.GET.get('q', '').strip()

    if selected_category:
        products = products.filter(catigoriya_id=selected_category)
    if search_query:
        products = products.filter(nom__icontains=search_query)

    favorite_ids = list(
        Sevimli.objects.filter(user=request.user).values_list('produkt_id', flat=True)
    )
    cart_data = _serialize_user_cart(request.user)

    return render(request, 'produkt/home.html', {
        'profile': profile,
        'show_splash': show_splash,
        'categories': categories,
        'products': products,
        'selected_category': selected_category,
        'search_query': search_query,
        'total_products_count': Produkt.objects.count(),
        'favorite_ids_json': json.dumps(favorite_ids),
        'initial_cart_json': json.dumps(cart_data),
    })


@login_required
def cart_api_view(request):
    return JsonResponse({'ok': True, **_serialize_user_cart(request.user)})


@login_required
@require_POST
def cart_update_view(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        pid = int(payload.get('produkt_id'))
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': "Noto'g'ri ma'lumot."}, status=400)

    product = get_object_or_404(Produkt, id=pid)
    delta = payload.get('delta')
    explicit_qty = payload.get('quantity')

    entry, created = SavatchaItem.objects.get_or_create(
        user=request.user,
        produkt=product,
        defaults={'quantity': 0},
    )

    if explicit_qty is not None:
        try:
            new_qty = int(explicit_qty)
        except (TypeError, ValueError):
            new_qty = entry.quantity
    elif delta is not None:
        try:
            new_qty = entry.quantity + int(delta)
        except (TypeError, ValueError):
            new_qty = entry.quantity
    else:
        new_qty = entry.quantity + 1

    if new_qty <= 0:
        entry.delete()
    else:
        entry.quantity = new_qty
        entry.save(update_fields=['quantity', 'updated_at'])

    return JsonResponse({'ok': True, **_serialize_user_cart(request.user)})


@login_required
@require_POST
def toggle_favorite_view(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        pid = int(payload.get('produkt_id'))
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': "Noto'g'ri ma'lumot."}, status=400)

    product = get_object_or_404(Produkt, id=pid)
    fav = Sevimli.objects.filter(user=request.user, produkt=product).first()
    if fav:
        fav.delete()
        is_fav = False
    else:
        Sevimli.objects.create(user=request.user, produkt=product)
        is_fav = True

    favorite_ids = list(
        Sevimli.objects.filter(user=request.user).values_list('produkt_id', flat=True)
    )
    return JsonResponse({
        'ok': True,
        'is_favorite': is_fav,
        'favorite_ids': favorite_ids,
    })


def _serialize_reviews(product):
    reviews = product.izohlar.select_related('user').all()[:25]
    agg = product.izohlar.aggregate(avg=Avg('rating'), cnt=Count('id'))
    avg = round(float(agg['avg']), 1) if agg['avg'] else 0
    return {
        'avg_rating': avg,
        'review_count': agg['cnt'] or 0,
        'reviews': [
            {
                'id': r.id,
                'author': r.user.first_name or r.user.username,
                'rating': r.rating,
                'comment': r.comment,
                'created_at': r.created_at.strftime('%d.%m.%Y %H:%M'),
            }
            for r in reviews
        ],
    }


@login_required
def product_reviews_view(request, produkt_id):
    product = get_object_or_404(Produkt, id=produkt_id)
    return JsonResponse({'ok': True, **_serialize_reviews(product)})


@login_required
@require_POST
def add_product_review_view(request, produkt_id):
    product = get_object_or_404(Produkt, id=produkt_id)
    try:
        payload = json.loads(request.body.decode('utf-8'))
        rating = int(payload.get('rating', 5))
        comment = (payload.get('comment') or '').strip()
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': "Noto'g'ri ma'lumot."}, status=400)

    rating = max(1, min(5, rating))
    if not comment:
        return JsonResponse({'ok': False, 'error': "Iltimos, izoh matnini yozing."}, status=400)

    ProduktIzoh.objects.create(
        produkt=product,
        user=request.user,
        rating=rating,
        comment=comment,
    )
    return JsonResponse({'ok': True, **_serialize_reviews(product)})


@login_required
@require_POST
def submit_contact_view(request):
    profile = _get_or_create_profile(request.user)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        payload = request.POST

    name = (payload.get('name') or profile.display_name).strip()
    phone = (payload.get('phone') or profile.telefon or '').strip()
    message = (payload.get('message') or '').strip()

    if not message:
        return JsonResponse({'ok': False, 'error': "Iltimos, xabar matnini kiriting."}, status=400)

    Murojaat.objects.create(
        user=request.user,
        name=name,
        phone=phone,
        message=message,
    )
    return JsonResponse({
        'ok': True,
        'message': "Murojaatingiz bazaga saqlandi va adminga yuborildi! ✅",
    })


@login_required
@require_POST
def estimate_delivery_view(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        lat = Decimal(str(payload.get('latitude')))
        lng = Decimal(str(payload.get('longitude')))
        address_text = (payload.get('address_text') or '').strip()
    except (ValueError, TypeError, InvalidOperation, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': "Koordinata noto'g'ri."}, status=400)

    _, est_price = calculate_yandex_estimate(lat, lng, address_text=address_text)
    is_uchtepa = est_price == Decimal('50000')
    return JsonResponse({
        'ok': True,
        'delivery_price': str(est_price),
        'formatted_delivery_price': format_uzs(est_price),
        'zone_label': "Uchtepa tumani" if is_uchtepa else "Boshqa tuman",
    })


@login_required
@require_POST
def create_order_view(request):
    profile = _get_or_create_profile(request.user)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': "Noto'g'ri so'rov formati."}, status=400)

    items_payload = payload.get('items') or []
    lat_raw = payload.get('latitude')
    lng_raw = payload.get('longitude')
    address_text = (payload.get('address_text') or '').strip()
    phone = (payload.get('phone') or profile.telefon or '').strip()
    note = (payload.get('note') or '').strip()

    product_quantities = {}
    if items_payload:
        for entry in items_payload:
            try:
                pid = int(entry.get('id'))
                qty = int(entry.get('quantity', 0))
            except (TypeError, ValueError):
                continue
            if qty > 0:
                product_quantities[pid] = product_quantities.get(pid, 0) + qty
    else:
        for db_item in SavatchaItem.objects.filter(user=request.user):
            if db_item.quantity > 0:
                product_quantities[db_item.produkt_id] = db_item.quantity

    if not product_quantities:
        return JsonResponse({'ok': False, 'error': "Savatcha bo'sh!"}, status=400)

    try:
        lat = Decimal(str(lat_raw)).quantize(Decimal('0.000001'))
        lng = Decimal(str(lng_raw)).quantize(Decimal('0.000001'))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': "Iltimos, xaritadan joylashuvingizni tanlang."}, status=400)

    products_map = {p.id: p for p in Produkt.objects.filter(id__in=product_quantities.keys())}
    if not products_map:
        return JsonResponse({'ok': False, 'error': "Tanlangan mahsulotlar topilmadi."}, status=404)

    road_km, yandex_est = calculate_yandex_estimate(lat, lng, address_text=address_text)

    with transaction.atomic():
        items_total = Decimal('0')
        order = Buyurtma.objects.create(
            user=request.user,
            customer_name=profile.display_name,
            phone=phone,
            address_text=address_text or f"{lat}, {lng}",
            latitude=lat,
            longitude=lng,
            note=note,
            distance_km=road_km,
            yandex_estimated_delivery=yandex_est,
            delivery_price=yandex_est,
            status='new',
        )

        for pid, qty in product_quantities.items():
            product = products_map.get(pid)
            if not product:
                continue
            BuyurtmaItem.objects.create(
                buyurtma=order,
                produkt=product,
                product_name=product.nom,
                unit_price=product.narx,
                quantity=qty,
            )
            items_total += Decimal(str(product.narx)) * qty

        order.items_total = items_total
        order.save(update_fields=['items_total'])
        SavatchaItem.objects.filter(user=request.user).delete()

    return JsonResponse({
        'ok': True,
        'order_id': order.id,
        'message': "Adminga zakas tushdi! Buyurtmangiz muvaffaqiyatli yuborildi ✅",
        'delivery_price': order.formatted_delivery_price,
    })


@login_required
def orders_view(request):
    profile = _get_or_create_profile(request.user)
    is_admin_user = _is_site_admin(request.user)

    if is_admin_user:
        orders = Buyurtma.objects.select_related('user').prefetch_related('items').all()
        inquiries = Murojaat.objects.select_related('user').all()[:20]
    else:
        orders = Buyurtma.objects.filter(user=request.user).prefetch_related('items')
        inquiries = []

    latest_order = orders.first()
    return render(request, 'produkt/orders.html', {
        'profile': profile,
        'orders': orders,
        'inquiries': inquiries,
        'is_admin_user': is_admin_user,
        'latest_order_id': latest_order.id if latest_order else 0,
        'status_choices': Buyurtma.STATUS_CHOICES,
    })


@login_required
@require_POST
def update_order_delivery_view(request, order_id):
    if not _is_site_admin(request.user):
        return HttpResponseForbidden("Faqat tuzlama.uz admini dastafka narxini belgilashi mumkin.")

    order = get_object_or_404(Buyurtma, id=order_id)
    price_raw = (request.POST.get('delivery_price') or '').replace(' ', '').strip()
    new_status = request.POST.get('status') or order.status

    valid_statuses = {code for code, _ in Buyurtma.STATUS_CHOICES}
    if new_status not in valid_statuses:
        new_status = order.status

    if price_raw:
        try:
            price_val = Decimal(price_raw)
            if price_val < 0:
                raise InvalidOperation()
            order.delivery_price = price_val
            if order.status == 'new' and new_status == 'new':
                new_status = 'priced'
        except InvalidOperation:
            messages.error(request, "Dastafka narxi noto'g'ri kiritildi.")
            return redirect('orders')

    order.status = new_status
    order.save()
    messages.success(request, f"Buyurtma #{order.id} uchun dastafka narxi va holati saqlandi!")
    return redirect('orders')


@login_required
@require_POST
def update_my_order_location_view(request, order_id):
    order = get_object_or_404(Buyurtma, id=order_id)
    if order.user != request.user and not _is_site_admin(request.user):
        return HttpResponseForbidden("Siz faqat o'zingizning buyurtmangiz manzilini o'zgartira olasiz.")

    if order.status != 'new' and not _is_site_admin(request.user):
        messages.error(request, "Tasdiqlangan buyurtma manzilini o'zgartirib bo'lmaydi.")
        return redirect('orders')

    lat_raw = (request.POST.get('latitude') or '').strip()
    lng_raw = (request.POST.get('longitude') or '').strip()
    address_text = (request.POST.get('address_text') or '').strip()

    try:
        lat = Decimal(lat_raw).quantize(Decimal('0.000001'))
        lng = Decimal(lng_raw).quantize(Decimal('0.000001'))
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, "Koordinata noto'g'ri kiritildi.")
        return redirect('orders')

    road_km, est_price = calculate_yandex_estimate(lat, lng, address_text=address_text)
    order.latitude = lat
    order.longitude = lng
    order.address_text = address_text or f"{lat}, {lng}"
    order.distance_km = road_km
    order.yandex_estimated_delivery = est_price
    if order.status == 'new':
        order.delivery_price = est_price
    order.save()

    messages.success(request, f"Buyurtma #{order.id} manzili yangilandi!")
    return redirect('orders')


@login_required
def orders_poll_view(request):
    if _is_site_admin(request.user):
        latest = Buyurtma.objects.order_by('-id').values_list('id', flat=True).first() or 0
        new_count = Buyurtma.objects.filter(status='new').count()
    else:
        latest = Buyurtma.objects.filter(user=request.user).order_by('-id').values_list('id', flat=True).first() or 0
        new_count = Buyurtma.objects.filter(user=request.user).exclude(status__in=['completed', 'cancelled']).count()

    return JsonResponse({
        'latest_id': latest,
        'new_count': new_count,
    })
