from django.test import TestCase, Client
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django_tenants.utils import get_tenant_model
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from resources.models import Treatment, TreatmentStage, RiskEvaluation, InformationAssets, RiskEvaluation, AssetAction
from resources.forms import TreatmentForm, RiskEvaluationForm
from django.utils import timezone

User = get_user_model()

class TreatmentFlowTests(TenantTestCase):
    def setUp(self):
        # create users
        self.staff = User.objects.create_user('staff', 'staff@example.com', 'pass')
        self.staff.is_staff = True
        self.staff.save()

        self.resp = User.objects.create_user('resp', 'resp@example.com', 'pass')

        # create an information asset to link to
        self.asset = InformationAssets.objects.create(name='Test Asset', owner='owner')

        # create a treatment
        ct = ContentType.objects.get_for_model(self.asset)
        self.treatment = Treatment.objects.create(
            name='T1',
            content_type=ct,
            object_id=self.asset.pk,
            deadline=timezone.now().date() + timezone.timedelta(days=7),
            treatment_responsible=self.resp,
        )

        self.client = TenantClient(schema_name=self.tenant.schema_name)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_set_stage_helper(self):
        # initial is PENDING
        self.assertEqual(self.treatment.stage, TreatmentStage.PENDING)
        # change stage with helper
        self.treatment.set_stage(TreatmentStage.ANALYSIS, user=self.staff)
        t = Treatment.objects.get(pk=self.treatment.pk)
        self.assertEqual(t.stage, TreatmentStage.ANALYSIS)
        self.assertIsNotNone(t.stage_changed_at)
        self.assertEqual(t.stage_changed_by.pk, self.staff.pk)

    def test_advance_stage_view_permissions(self):
        url = reverse('treatment-advance', args=[self.treatment.pk])
        # anonymous cannot post
        resp = self.client.post(url, {'stage': TreatmentStage.IN_PROGRESS})
        self.assertIn(resp.status_code, (302, 403))

        # login as unrelated user -> should be forbidden
        self.client.login(username='staff', password='pass')
        resp = self.client.post(url, {'stage': TreatmentStage.IN_PROGRESS})
        # staff user is allowed
        self.assertEqual(resp.status_code, 302)

        self.client.logout()
        # login as responsible user
        self.client.login(username='resp', password='pass')
        resp = self.client.post(url, {'stage': TreatmentStage.IN_PROGRESS})
        self.assertEqual(resp.status_code, 302)

    def test_signal_creates_followup_evaluation(self):
        # ensure there is no evaluation initially
        self.assertEqual(RiskEvaluation.objects.filter(evaluated_type=self.treatment.content_type, evaluated_id=self.treatment.object_id).count(), 0)
        # create a base evaluation
        base = RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type,
            evaluated_id=self.treatment.object_id,
            threat_id=1 if hasattr(self, 'threat') else None,
            vulnerability_id=1 if hasattr(self, 'vulnerability') else None,
            description='base',
        )
        # advance stage to IMPLEMENTED which should trigger a follow-up
        self.treatment.set_stage(TreatmentStage.IMPLEMENTED, user=self.staff)
        # there should be a re-evaluation created
        self.assertTrue(RiskEvaluation.objects.filter(description__icontains='Re-evaluación').exists())


class AssetActionFlowTests(TenantTestCase):
    def setUp(self):
        User = get_user_model()
        self.client = TenantClient(schema_name=self.tenant.schema_name)
        # create users
        self.perf = User.objects.create_user(username='actor2', email='actor2@example.com', password='pass')
        self.benef = User.objects.create_user(username='benef2', email='benef2@example.com', password='pass')
        self.other = User.objects.create_user(username='other2', email='other2@example.com', password='pass')
        # create an asset
        self.asset = InformationAssets.objects.create(name='Laptop B', owner='Org')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_loan_confirmation_sets_holder(self):
        # perform loan request as performer
        self.client.force_login(self.perf)
        url = reverse('asset-loan')
        resp = self.client.post(url, {
            'asset': self.asset.pk,
            'user': self.benef.pk,
            'description': 'Necesita para viaje',
            'due_date': (timezone.now().date() + timezone.timedelta(days=7)).isoformat(),
        })
        self.assertIn(resp.status_code, (302, 200))
        aa = AssetAction.objects.filter(asset=self.asset).order_by('-timestamp').first()
        self.assertIsNotNone(aa)
        self.assertEqual(aa.status, 'PENDING')
        # confirm via token
        confirm_url = reverse('asset-action-confirm', args=[str(aa.confirmation_token)])
        resp2 = self.client.get(confirm_url)
        self.assertEqual(resp2.status_code, 200)
        aa.refresh_from_db()
        self.assertEqual(aa.status, 'CONFIRMED')
        # asset should now be loaned to beneficiary
        holder = self.asset.get_current_holder()
        self.assertIsNotNone(holder)
        self.assertEqual(holder.pk, self.benef.pk)
        self.assertTrue(self.asset.is_loaned)

    def test_return_without_confirmed_loan_rejected_on_confirm(self):
        # create a pending return
        self.client.force_login(self.perf)
        url = reverse('asset-return')
        resp = self.client.post(url, {
            'asset': self.asset.pk,
            'description': 'Devolución solicitada',
        })
        self.assertIn(resp.status_code, (302, 200))
        aa = AssetAction.objects.filter(asset=self.asset).order_by('-timestamp').first()
        self.assertEqual(aa.action_type, 1)  # RETURN
        self.assertEqual(aa.status, 'PENDING')
        # try to confirm -> should be rejected because no confirmed loan exists
        confirm_url = reverse('asset-action-confirm', args=[str(aa.confirmation_token)])
        resp2 = self.client.get(confirm_url)
        self.assertEqual(resp2.status_code, 400)
        aa.refresh_from_db()
        self.assertEqual(aa.status, 'REJECTED')
        self.assertFalse(self.asset.is_loaned)

    def test_double_confirmed_loan_rejected(self):
        # create and confirm an initial loan
        first = AssetAction.objects.create(asset=self.asset, action_type=0, user=self.benef, performed_by=self.perf, status='CONFIRMED')
        # request a second loan
        self.client.force_login(self.perf)
        url = reverse('asset-loan')
        resp = self.client.post(url, {
            'asset': self.asset.pk,
            'user': self.other.pk,
            'description': 'Segundo préstamo',
        })
        self.assertIn(resp.status_code, (302, 200))
        aa = AssetAction.objects.filter(asset=self.asset).order_by('-timestamp').first()
        self.assertEqual(aa.status, 'PENDING')
        # confirm second -> should be rejected because asset already confirmed loaned
        confirm_url = reverse('asset-action-confirm', args=[str(aa.confirmation_token)])
        resp2 = self.client.get(confirm_url)
        self.assertEqual(resp2.status_code, 400)
        aa.refresh_from_db()
        self.assertEqual(aa.status, 'REJECTED')
        # holder remains original
        holder = self.asset.get_current_holder()
        self.assertEqual(holder.pk, self.benef.pk)
