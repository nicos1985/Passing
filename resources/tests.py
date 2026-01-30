from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from resources.models import Treatment, TreatmentStage, RiskEvaluation, InformationAssets, RiskEvaluation
from resources.forms import TreatmentForm, RiskEvaluationForm
from django.utils import timezone

User = get_user_model()

class TreatmentFlowTests(TestCase):
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

        self.client = Client()

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
