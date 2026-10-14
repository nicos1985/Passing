from django.test import TestCase, Client, override_settings
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django_tenants.utils import get_tenant_model
from django.urls import reverse, set_urlconf
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from resources.models import Treatment, TreatmentStage, RiskEvaluation, InformationAssets, AssetAction, AssetType, Threat, Vulnerability, Vendor, ChecklistTemplate, ChecklistItem, VendorChecklist, VendorEvaluation
from resources.forms import TreatmentForm, RiskEvaluationForm, LoanForm, ReturnForm
from django.utils import timezone
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext

User = get_user_model()

@override_settings(ROOT_URLCONF="passing.urls_tenant")
class TreatmentFlowTests(TenantTestCase):
    def setUp(self):
        set_urlconf("passing.urls_tenant")
        self.addCleanup(set_urlconf, None)
        # create users
        self.staff = User.objects.create_user('staff', 'staff@example.com', 'pass', client=self.tenant)
        self.staff.is_staff = True
        self.staff.save()

        self.resp = User.objects.create_user('resp', 'resp@example.com', 'pass', client=self.tenant)

        # create an information asset to link to
        self.asset = InformationAssets.objects.create(name='Test Asset', owner=self.staff, asset_type=AssetType.PC_OR_NOTEBOOK)
        self.threat = Threat.objects.create(name='Amenaza de prueba')
        self.vulnerability = Vulnerability.objects.create(name='Vulnerabilidad de prueba')

        # create a treatment
        ct = ContentType.objects.get_for_model(self.asset)
        self.treatment = Treatment.objects.create(
            name='T1',
            content_type=ct,
            object_id=self.asset.pk,
            deadline=timezone.now().date() + timezone.timedelta(days=7),
            treatment_responsible=self.resp,
        )

        self.client = TenantClient(self.tenant)

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
            threat=self.threat,
            vulnerability=self.vulnerability,
            description='base',
            treatment=self.treatment,
        )
        # advance stage to IMPLEMENTED which should trigger a follow-up
        self.treatment.set_stage(TreatmentStage.IMPLEMENTED, user=self.staff)
        # there should be a re-evaluation created
        followup = RiskEvaluation.objects.get(followup_for=self.treatment)
        self.assertTrue(followup.is_draft)
        self.assertEqual(followup.risk_value, base.risk_value)

    def test_followup_preserves_original_link_and_is_idempotent(self):
        original = RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type,
            evaluated_id=self.treatment.object_id,
            threat=self.threat,
            vulnerability=self.vulnerability,
            treatment=self.treatment,
        )
        self.treatment.set_stage(TreatmentStage.IMPLEMENTED, user=self.staff)
        followup = RiskEvaluation.objects.get(followup_for=self.treatment)
        self.assertNotEqual(followup.pk, original.pk)
        original.refresh_from_db()
        self.assertEqual(original.treatment_id, self.treatment.pk)
        self.treatment.name = 'Tratamiento editado'
        self.treatment.save()
        self.assertEqual(RiskEvaluation.objects.filter(followup_for=self.treatment).count(), 1)

    def test_unlinked_treatment_does_not_copy_unrelated_evaluation(self):
        RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type, evaluated_id=self.asset.pk,
            threat=self.threat, vulnerability=self.vulnerability,
        )
        self.treatment.set_stage(TreatmentStage.IMPLEMENTED, user=self.staff)
        self.assertFalse(RiskEvaluation.objects.filter(followup_for=self.treatment).exists())

    def test_risk_history_blocks_catalog_treatment_and_resource_deletion(self):
        RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type, evaluated_id=self.asset.pk,
            threat=self.threat, vulnerability=self.vulnerability, treatment=self.treatment,
        )
        with self.assertRaises(ProtectedError):
            self.threat.delete()
        with self.assertRaises(ProtectedError):
            self.vulnerability.delete()
        with self.assertRaises(ProtectedError):
            self.treatment.delete()
        with self.assertRaises(ProtectedError):
            self.asset.delete()

    def test_protected_delete_returns_to_list_without_losing_history(self):
        RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type, evaluated_id=self.asset.pk,
            threat=self.threat, vulnerability=self.vulnerability,
        )
        self.client.force_login(self.staff)
        response = self.client.post(reverse('threat-delete', args=[self.threat.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Threat.objects.filter(pk=self.threat.pk).exists())
        self.assertEqual(RiskEvaluation.objects.count(), 1)

    def test_risk_form_rejects_treatment_of_another_resource(self):
        other = InformationAssets.objects.create(name='Otro activo', owner=self.staff, asset_type=AssetType.PC_OR_NOTEBOOK)
        form = RiskEvaluationForm(data={
            'model_type': self.treatment.content_type_id,
            'object_id': other.pk,
            'threat': self.threat.pk,
            'vulnerability': self.vulnerability.pk,
            'confidenciality_impact': 1,
            'integrity_impact': 1,
            'availability_impact': 1,
            'probability': 1,
            'treatment': self.treatment.pk,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('treatment', form.errors)

    def test_risk_read_requires_permission(self):
        url = reverse('evaluation-list')
        self.client.force_login(self.resp)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_risk_and_treatment_lists_show_compact_columns(self):
        RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type,
            evaluated_id=self.asset.pk,
            threat=self.threat,
            vulnerability=self.vulnerability,
        )
        self.client.force_login(self.staff)
        risk_response = self.client.get(reverse('evaluation-list'))
        self.assertEqual(risk_response.status_code, 200)
        self.assertContains(risk_response, 'Test Asset')
        self.assertEqual(
            [field['name'] for field in risk_response.context['fields']],
            ['evaluated_id', 'threat', 'vulnerability', 'risk_level', 'is_draft', 'treatment'],
        )
        self.assertNotIn('>check<', risk_response.content.decode())

        treatment_response = self.client.get(reverse('treatment-list', urlconf='passing.urls_tenant'))
        self.assertEqual(treatment_response.status_code, 200)
        self.assertEqual(
            [field['name'] for field in treatment_response.context['fields']],
            ['name', 'object_id', 'stage', 'treatment_responsible', 'priority', 'deadline'],
        )

    def test_orphan_evaluation_detail_is_readable(self):
        evaluation = RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type, evaluated_id=self.asset.pk,
            threat=self.threat, vulnerability=self.vulnerability,
        )
        RiskEvaluation.objects.filter(pk=evaluation.pk).update(evaluated_id=999999)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('evaluation-detail', args=[evaluation.pk])).status_code, 200)

    def test_vulnerability_default_is_valid_choice(self):
        self.assertEqual(self.vulnerability.type_vulnerability, 8)

    def test_treatment_form_limits_responsible_to_tenant(self):
        outsider = User.objects.create_user('outsider', 'outsider@example.com', 'pass')
        form = TreatmentForm(instance=self.treatment)
        responsible_ids = set(form.fields['treatment_responsible'].queryset.values_list('pk', flat=True))
        self.assertIn(self.resp.pk, responsible_ids)
        self.assertNotIn(outsider.pk, responsible_ids)

    def test_creating_treatment_from_evaluation_links_it(self):
        evaluation = RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type, evaluated_id=self.asset.pk,
            threat=self.threat, vulnerability=self.vulnerability,
        )
        self.client.force_login(self.staff)
        response = self.client.post(reverse('treatment-create'), {
            'evaluation_id': evaluation.pk,
            'model_type': self.treatment.content_type_id,
            'object_id': self.asset.pk,
            'name': 'Tratamiento vinculado',
            'treatment_type': self.treatment.treatment_type,
            'controls': self.treatment.controls,
            'deadline': (timezone.now().date() + timezone.timedelta(days=7)).isoformat(),
            'treatment_responsible': self.resp.pk,
            'treatment_oportunity': self.treatment.treatment_oportunity,
            'application_periodicity': self.treatment.application_periodicity,
            'control_automation': self.treatment.control_automation,
            'priority': self.treatment.priority,
            'stage': TreatmentStage.PENDING,
        })
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        evaluation.refresh_from_db()
        self.assertIsNotNone(evaluation.treatment_id)
        self.assertEqual(evaluation.treatment.name, 'Tratamiento vinculado')

    def test_followup_requires_review_before_it_is_confirmed(self):
        RiskEvaluation.objects.create(
            evaluated_type=self.treatment.content_type, evaluated_id=self.asset.pk,
            threat=self.threat, vulnerability=self.vulnerability,
            treatment=self.treatment,
        )
        self.treatment.set_stage(TreatmentStage.IMPLEMENTED, user=self.staff)
        followup = RiskEvaluation.objects.get(followup_for=self.treatment)
        self.assertTrue(followup.is_draft)
        self.client.force_login(self.staff)
        response = self.client.post(reverse('evaluation-update', args=[followup.pk]), {
            'model_type': self.treatment.content_type_id,
            'object_id': self.asset.pk,
            'threat': self.threat.pk,
            'vulnerability': self.vulnerability.pk,
            'description': 'Revisado',
            'confidenciality_impact': 1,
            'integrity_impact': 1,
            'availability_impact': 1,
            'probability': 1,
            'treatment': '',
        })
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        followup.refresh_from_db()
        self.assertFalse(followup.is_draft)
        self.assertIsNotNone(followup.reviewed_at)
        self.assertEqual(followup.reviewed_by_id, self.staff.pk)

    def test_treatment_edit_keeps_selected_resource(self):
        form = TreatmentForm(instance=self.treatment)
        self.assertIn(str(self.asset.pk), [value for value, _ in form.fields['object_id'].choices])

    def test_stage_notes_are_saved_and_invalid_stage_is_rejected(self):
        self.client.force_login(self.staff)
        url = reverse('treatment-advance', args=[self.treatment.pk])
        self.client.post(url, {
            'stage': TreatmentStage.PENDING,
            'analysis_notes': 'Revisar acceso',
        })
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.analysis_notes, 'Revisar acceso')
        self.client.post(url, {'stage': 999})
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.stage, TreatmentStage.PENDING)


@override_settings(ROOT_URLCONF="passing.urls_tenant")
class AssetActionFlowTests(TenantTestCase):
    def setUp(self):
        set_urlconf("passing.urls_tenant")
        self.addCleanup(set_urlconf, None)
        User = get_user_model()
        self.client = TenantClient(self.tenant)
        # create users
        self.perf = User.objects.create_user(username='actor2', email='actor2@example.com', password='pass', client=self.tenant)
        self.perf.is_staff = True
        self.perf.save(update_fields=['is_staff'])
        self.benef = User.objects.create_user(username='benef2', email='benef2@example.com', password='pass', client=self.tenant)
        self.other = User.objects.create_user(username='other2', email='other2@example.com', password='pass', client=self.tenant)
        # create an asset
        self.asset = InformationAssets.objects.create(name='Laptop B', owner=self.perf, asset_type=AssetType.PC_OR_NOTEBOOK)

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
        confirm_url = reverse('asset-action-confirm', args=[str(aa.confirmation_token)], urlconf="passing.urls_tenant")
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(confirm_url).status_code, 403)
        self.client.force_login(self.benef)
        resp2 = self.client.get(confirm_url)
        self.assertEqual(resp2.status_code, 200)
        aa.refresh_from_db()
        self.assertEqual(aa.status, 'PENDING')
        resp2 = self.client.post(confirm_url)
        self.assertEqual(resp2.status_code, 200)
        aa.refresh_from_db()
        self.assertEqual(aa.status, 'CONFIRMED')
        self.assertIsNone(aa.confirmation_token)
        # asset should now be loaned to beneficiary
        holder = self.asset.get_current_holder()
        self.assertIsNotNone(holder)
        self.assertEqual(holder.pk, self.benef.pk)
        self.assertTrue(self.asset.is_loaned)

    def test_unprivileged_user_cannot_create_resource_or_read_arbitrary_models(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('informationassets-create')).status_code, 403)
        other_type = ContentType.objects.get_for_model(User)
        response = self.client.get(reverse('ajax-get-objects', urlconf='passing.urls_tenant'), {'type_id': other_type.pk})
        self.assertEqual(response.status_code, 400)

    def test_asset_choice_queries_do_not_scale_per_asset(self):
        for index in range(5):
            InformationAssets.objects.create(name=f'Laptop {index}', owner=self.perf, asset_type=AssetType.PC_OR_NOTEBOOK)
        with self.assertNumQueries(0):
            loan_form = LoanForm()
            return_form = ReturnForm()
        with CaptureQueriesContext(connection) as queries:
            list(loan_form.fields['asset'].queryset)
            list(return_form.fields['asset'].queryset)
        asset_selects = [query for query in queries if 'FROM "resources_informationassets"' in query['sql']]
        self.assertEqual(len(asset_selects), 2)

    def test_vendor_schedule_copies_checklist_once(self):
        template = ChecklistTemplate.objects.create(name='Seguridad')
        ChecklistItem.objects.create(template=template, text='¿Usa MFA?')
        vendor = Vendor.objects.create(
            name='Proveedor', owner=self.perf, start_date=timezone.localdate(),
        )
        VendorChecklist.objects.create(vendor=vendor, template=template)
        evaluation = vendor.schedule_next_evaluation()
        self.assertIsNotNone(evaluation)
        self.assertEqual(evaluation.items.count(), 1)

    def test_resource_dates_retain_creation_time(self):
        old_created = timezone.now() - timezone.timedelta(days=2)
        InformationAssets.objects.filter(pk=self.asset.pk).update(created=old_created)
        self.asset.refresh_from_db()
        self.asset.description = 'Actualizado'
        old_acquisition = timezone.localdate() - timezone.timedelta(days=365)
        self.asset.acquisition_date = old_acquisition
        self.asset.save()
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.created, old_created)
        self.assertGreater(self.asset.updated, old_created)
        self.assertEqual(self.asset.acquisition_date, old_acquisition)

    def test_return_without_confirmed_loan_rejected_on_confirm(self):
        # The form rejects returns for assets without a confirmed loan.
        self.client.force_login(self.perf)
        url = reverse('asset-return')
        resp = self.client.post(url, {
            'asset': self.asset.pk,
            'description': 'Devolución solicitada',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(AssetAction.objects.filter(asset=self.asset).exists())
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
        self.assertEqual(AssetAction.objects.filter(asset=self.asset).count(), 1)
        # holder remains original
        holder = self.asset.get_current_holder()
        self.assertEqual(holder.pk, self.benef.pk)
