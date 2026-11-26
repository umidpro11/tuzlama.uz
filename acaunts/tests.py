import json
import tempfile
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from acaunts.models import Profile
from catigoriya.models import Catigoriya
from produkt.models import Buyurtma, Murojaat, Produkt, ProduktIzoh, SavatchaItem, Sevimli


def make_test_image(name='test.png'):
    buf = BytesIO()
    Image.new('RGB', (10, 10), color=(30, 120, 60)).save(buf, format='PNG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/png')


TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class TuzlamaSiteTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_requires_login(self):
        resp = self.client.get(reverse('home'))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('home')}")

    def test_register_login_splash_and_profile_flow(self):
        # Register mismatch
        resp_bad = self.client.post(reverse('register'), {
            'ism': 'Azizbek',
            'parol1': 'salom123',
            'parol2': 'salom124',
        })
        self.assertEqual(resp_bad.status_code, 200)
        self.assertFalse(User.objects.filter(username='Azizbek').exists())

        # Register matching (even simple password should succeed)
        resp_ok = self.client.post(reverse('register'), {
            'ism': 'Azizbek',
            'parol1': '1234',
            'parol2': '1234',
        })
        self.assertRedirects(resp_ok, reverse('login'))
        self.assertTrue(User.objects.filter(username='Azizbek').exists())

        # Login redirects to home with fullscreen splash once
        resp_home1 = self.client.post(reverse('login'), {
            'ism': 'Azizbek',
            'parol': '1234',
        }, follow=True)
        self.assertEqual(resp_home1.status_code, 200)
        self.assertContains(resp_home1, 'id="welcomeSplash"')
        self.assertContains(resp_home1, 'tuzlama.uz')
        self.assertContains(resp_home1, 'Azizbek')

        # Second visit does not repeat splash
        resp_home2 = self.client.get(reverse('home'))
        self.assertNotContains(resp_home2, 'id="welcomeSplash"')

        # Profile update
        resp_prof = self.client.post(reverse('profile'), {
            'ism': 'Azizbek',
            'familiya': 'Karimov',
            'telefon': '+998901234567',
            'avatar': make_test_image('avatar.png'),
        })
        self.assertRedirects(resp_prof, reverse('profile'))

        profile = Profile.objects.get(user__username='Azizbek')
        self.assertEqual(profile.familiya, 'Karimov')
        self.assertEqual(profile.telefon, '+998901234567')
        self.assertTrue(bool(profile.avatar))

        resp_prof_get = self.client.get(reverse('profile'))
        self.assertContains(resp_prof_get, 'Karimov')
        self.assertContains(resp_prof_get, '+998901234567')

    def test_admin_fields_and_product_display(self):
        cat_admin = site._registry[Catigoriya]
        prod_admin = site._registry[Produkt]

        self.assertEqual(cat_admin.fields, ('nom',))
        self.assertEqual(prod_admin.fields, ('nom', 'catigoriya', 'narx', 'about', 'rasm'))

        cat = Catigoriya.objects.create(nom='Bodring tuzlamalari')
        prod = Produkt.objects.create(
            nom='Qarsildoq bodring',
            catigoriya=cat,
            narx=25000,
            about='Tabiiy uy retsepti asosida tayyorlangan.',
            rasm=make_test_image('bodring.png'),
        )

        User.objects.create_user(username='Ali', password='123')
        self.client.login(username='Ali', password='123')
        resp = self.client.get(reverse('home'))
        self.assertContains(resp, 'Bodring tuzlamalari')
        self.assertContains(resp, 'Qarsildoq bodring')
        self.assertContains(resp, '25 000')
        self.assertEqual(prod.formatted_narx, '25 000')

    def test_admin_button_only_visible_to_tuzlama_uz(self):
        User.objects.create_user(username='Umidjon', password='123', is_staff=True)
        User.objects.create_user(username='tuzlama.uz', password='123')

        self.client.login(username='Umidjon', password='123')
        resp_other = self.client.get(reverse('home'))
        self.assertNotContains(resp_other, 'Admin Panel')

        self.client.login(username='tuzlama.uz', password='123')
        resp_owner = self.client.get(reverse('home'))
        self.assertContains(resp_owner, 'Admin Panel ↗')

    def test_order_creation_and_admin_delivery_pricing(self):
        cat = Catigoriya.objects.create(nom='Pomidor')
        prod = Produkt.objects.create(
            nom='Qizil pomidor tuzlama',
            catigoriya=cat,
            narx=30000,
            about='Mazali uy tuzlamasi',
            rasm=make_test_image('pomidor.png'),
        )
        buyer = User.objects.create_user(username='Umidjon', password='123')
        other_buyer = User.objects.create_user(username='tuzlama', password='123', is_staff=True)
        admin_owner = User.objects.create_user(username='tuzlama.uz', password='123')

        # Navbar has Buyurtmalar instead of Mahsulotlar
        self.client.login(username='Umidjon', password='123')
        home_resp = self.client.get(reverse('home'))
        self.assertContains(home_resp, 'Buyurtmalar')
        self.assertNotContains(home_resp, '>Mahsulotlar<')

        # DB-backed cart, favorites, reviews, and contact inquiries
        cart_resp = self.client.post(
            reverse('cart_update'),
            data=json.dumps({'produkt_id': prod.id, 'delta': 2}),
            content_type='application/json',
        )
        self.assertEqual(cart_resp.status_code, 200)
        self.assertEqual(SavatchaItem.objects.get(user=buyer, produkt=prod).quantity, 2)

        fav_resp = self.client.post(
            reverse('toggle_favorite'),
            data=json.dumps({'produkt_id': prod.id}),
            content_type='application/json',
        )
        self.assertEqual(fav_resp.status_code, 200)
        self.assertTrue(Sevimli.objects.filter(user=buyer, produkt=prod).exists())

        rev_resp = self.client.post(
            reverse('add_product_review', args=[prod.id]),
            data=json.dumps({'rating': 5, 'comment': 'Juda mazali!'}),
            content_type='application/json',
        )
        self.assertEqual(rev_resp.status_code, 200)
        self.assertTrue(ProduktIzoh.objects.filter(produkt=prod, user=buyer, rating=5).exists())

        contact_resp = self.client.post(
            reverse('submit_contact'),
            data=json.dumps({'name': 'Umidjon', 'phone': '+998901112233', 'message': 'Yangi tuzlama bormi?'}),
            content_type='application/json',
        )
        self.assertEqual(contact_resp.status_code, 200)
        self.assertTrue(Murojaat.objects.filter(user=buyer, message='Yangi tuzlama bormi?').exists())

        # Uchtepa delivery price should be 50 000
        uchtepa_resp = self.client.post(
            reverse('create_order'),
            data=json.dumps({
                'items': [{'id': prod.id, 'quantity': 1}],
                'latitude': 41.3180,
                'longitude': 69.1880,
                'address_text': 'Toshkent, Uchtepa tumani, 12-kvartal',
                'phone': '+998901112233',
            }),
            content_type='application/json',
        )
        self.assertEqual(uchtepa_resp.status_code, 200)
        uchtepa_order = Buyurtma.objects.order_by('-id').first()
        self.assertEqual(uchtepa_order.delivery_price, Decimal('50000.00'))

        # Other district delivery price should be > 50 000 (in +10 000 increments)
        other_resp = self.client.post(
            reverse('create_order'),
            data=json.dumps({
                'items': [{'id': prod.id, 'quantity': 2}],
                'latitude': 41.3650,
                'longitude': 69.2850,
                'address_text': 'Yunusobod tumani, 4-mavze',
                'phone': '+998901112233',
                'note': 'Tezroq',
            }),
            content_type='application/json',
        )
        self.assertEqual(other_resp.status_code, 200)
        order = Buyurtma.objects.order_by('-id').first()
        self.assertEqual(order.user, buyer)
        self.assertEqual(order.items_total, Decimal('60000.00'))
        self.assertGreaterEqual(order.delivery_price, Decimal('60000.00'))
        self.assertEqual((order.delivery_price - Decimal('50000')) % Decimal('10000'), Decimal('0'))

        # Buyer sees own orders, does NOT see private store address
        buyer_orders = self.client.get(reverse('orders'))
        self.assertContains(buyer_orders, 'Yunusobod tumani')
        self.assertNotContains(buyer_orders, '5-pr Quvnoq')

        # Non-tuzlama.uz user (even staff) cannot see buyer's orders or set delivery price
        self.client.force_login(other_buyer)
        other_orders = self.client.get(reverse('orders'))
        self.assertNotContains(other_orders, 'Yunusobod tumani')
        self.assertNotContains(other_orders, '5-pr Quvnoq')

        forbid_resp = self.client.post(reverse('update_order_delivery', args=[order.id]), {
            'delivery_price': '55000',
            'status': 'priced',
        })
        self.assertEqual(forbid_resp.status_code, 403)

        forbid_loc = self.client.post(reverse('update_my_order_location', args=[order.id]), {
            'latitude': '41.3000',
            'longitude': '69.2000',
            'address_text': 'Hack',
        })
        self.assertEqual(forbid_loc.status_code, 403)

        # Buyer can update their own 'new' order location independently
        self.client.force_login(buyer)
        loc_ok = self.client.post(reverse('update_my_order_location', args=[order.id]), {
            'latitude': '41.3190',
            'longitude': '69.1890',
            'address_text': 'Uchtepa tumani, Farhod bozori',
        })
        self.assertRedirects(loc_ok, reverse('orders'))
        order.refresh_from_db()
        self.assertEqual(order.delivery_price, Decimal('50000.00'))

        # ONLY tuzlama.uz sees all orders and private store address, and sets delivery price
        self.client.force_login(admin_owner)
        orders_page = self.client.get(reverse('orders'))
        self.assertContains(orders_page, 'Uchtepa tumani, Farhod bozori')
        self.assertContains(orders_page, 'Umidjon')
        self.assertContains(orders_page, '5-pr Quvnoq, 30-uy')

        price_resp = self.client.post(reverse('update_order_delivery', args=[order.id]), {
            'delivery_price': '60000',
            'status': 'priced',
        })
        self.assertRedirects(price_resp, reverse('orders'))
        order.refresh_from_db()
        self.assertEqual(order.delivery_price, Decimal('60000.00'))
        self.assertEqual(order.grand_total, Decimal('120000.00'))
        self.assertEqual(order.status, 'priced')

        # Buyer now sees confirmed delivery price on /orders/
        self.client.force_login(buyer)
        buyer_orders_after = self.client.get(reverse('orders'))
        self.assertContains(buyer_orders_after, '60 000')
        self.assertContains(buyer_orders_after, '120 000')
