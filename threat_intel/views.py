from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, CreateView, UpdateView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.utils import timezone
from resources.views import DynamicModelListView
from .models import Run, RunItem, IntelItem, AIAnalysis, Report, Review, Source, TechTag
from .services.ai import analyze_relevant_items_for_run
from .services.emailer import send_report_email
from .services.report_generator import generate_report_pdf, generate_report_markdown, generate_report_json
from django.utils.text import capfirst
import csv
import json


class RunListView(LoginRequiredMixin, DynamicModelListView):
    model = Run
    template_name = 'threat_intel_run_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Run list does not support create/edit/delete, only view and export
        return context


class RunDetailView(LoginRequiredMixin, DetailView):
    model = Run
    template_name = 'threat_intel_run_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run = self.get_object()
        meta = run.__class__._meta

        # Fields display (from model introspection)
        visible_fields = []
        for field in meta.get_fields():
            if field.concrete and not field.many_to_many and not field.auto_created and field.name not in ['id']:
                if hasattr(field, 'choices') and field.choices:
                    display_method = f"get_{field.name}_display"
                    value = getattr(run, display_method)()
                else:
                    value = getattr(run, field.name, None)

                visible_fields.append({
                    'name': field.name,
                    'verbose_name': field.verbose_name.title(),
                    'value': value
                })

        context['fields'] = visible_fields
        context['verbose_model_name'] = meta.verbose_name.title()

        # list of RunItems for this run
        items = RunItem.objects.filter(run=run).select_related('item')
        context['run_items'] = items
        context['run_items_count'] = items.count()
        
        # helper urls
        context['rerun_url'] = reverse('threat_intel:run-rerun', args=[run.pk])
        context['export_url'] = reverse('threat_intel:run-export', args=[run.pk])
        context['items_url'] = reverse('threat_intel:runitem-list', args=[run.pk])
        context['back_url'] = reverse('threat_intel:run-list')
        context['edit_url'] = None  # Runs are not editable
        context['delete_url'] = None  # Hide delete for now
        return context


class RunRerunView(LoginRequiredMixin, View):
    def post(self, request, pk):
        run = get_object_or_404(Run, pk=pk)
        try:
            processed = analyze_relevant_items_for_run(run)
            messages.success(request, f'Re-análisis ejecutado. Items procesados: {processed}')
        except Exception as e:
            messages.error(request, f'Error al re-analizar: {e}')
        return redirect('threat_intel:run-detail', pk=pk)


class RunExportView(LoginRequiredMixin, View):
    def get(self, request, pk):
        run = get_object_or_404(Run, pk=pk)
        format = request.GET.get('format', 'csv')
        items = RunItem.objects.filter(run=run).select_related('item')

        if format == 'json':
            import json
            data = []
            for ri in items:
                it = ri.item
                data.append({
                    'canonical_id': it.canonical_id,
                    'title': it.title,
                    'severity': it.severity,
                    'cvss': str(it.cvss) if it.cvss is not None else '',
                    'primary_url': it.primary_url,
                })
            return HttpResponse(json.dumps(data, ensure_ascii=False), content_type='application/json')

        # default CSV
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="run_{run.pk}_items.csv"'
        writer = csv.writer(resp)
        writer.writerow(['canonical_id', 'title', 'severity', 'cvss', 'primary_url'])
        for ri in items:
            it = ri.item
            writer.writerow([it.canonical_id, it.title, it.severity, str(it.cvss) if it.cvss is not None else '', it.primary_url])
        return resp


class RunItemListView(LoginRequiredMixin, ListView):
    """List items found in a specific run."""
    model = RunItem
    template_name = 'threat_intel_runitem_list.html'
    paginate_by = 50
    context_object_name = 'run_items'

    def get_queryset(self):
        run_pk = self.kwargs.get('run_pk')
        self.run = get_object_or_404(Run, pk=run_pk)
        qs = RunItem.objects.filter(run=self.run).select_related('item')
        
        # Filtrar por severidad si viene en GET
        severity = self.request.GET.get('severity')
        if severity:
            qs = qs.filter(item__severity=severity)
        
        # Filtrar por relevancia
        is_relevant = self.request.GET.get('is_relevant')
        if is_relevant == 'true':
            qs = qs.filter(item__is_relevant=True)
        elif is_relevant == 'false':
            qs = qs.filter(item__is_relevant=False)
        
        return qs.order_by('-item__cvss')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['run'] = self.run
        context['back_url'] = reverse('threat_intel:run-detail', args=[self.run.pk])
        return context


class IntelItemDetailView(LoginRequiredMixin, DetailView):
    """Detail view for a single IntelItem (vulnerability)."""
    model = IntelItem
    template_name = 'threat_intel_item_detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        
        # Get related RunItems
        run_items = RunItem.objects.filter(item=item).select_related('run')
        context['run_items'] = run_items
        
        # Get AIAnalysis if exists
        run_pk = self.request.GET.get('run_pk')
        if run_pk:
            run = get_object_or_404(Run, pk=run_pk)
            analysis = AIAnalysis.objects.filter(item=item, run=run).first()
            context['analysis'] = analysis
            context['run'] = run
            context['back_url'] = reverse('threat_intel:runitem-list', args=[run.pk])
        else:
            context['back_url'] = reverse('threat_intel:run-list')
        
        # Display model fields
        meta = item.__class__._meta
        visible_fields = []
        for field in meta.get_fields():
            if field.concrete and not field.many_to_many and not field.auto_created and field.name not in ['id']:
                if field.name == 'references':
                    # Special handling for JSONField
                    value = getattr(item, field.name, [])
                    if isinstance(value, list):
                        value = ', '.join(value) if value else 'N/A'
                else:
                    value = getattr(item, field.name, None)

                visible_fields.append({
                    'name': field.name,
                    'verbose_name': field.verbose_name.title(),
                    'value': value
                })

        context['fields'] = visible_fields
        return context


class IntelItemToggleRelevantView(LoginRequiredMixin, View):
    """Toggle is_relevant flag on an IntelItem."""
    def post(self, request, pk):
        item = get_object_or_404(IntelItem, pk=pk)
        item.is_relevant = not item.is_relevant
        item.save()
        
        # Return to previous run or list
        run_pk = request.POST.get('run_pk')
        if run_pk:
            return redirect('threat_intel:runitem-list', run_pk=run_pk)
        return redirect('threat_intel:run-list')


class AIAnalysisListView(LoginRequiredMixin, ListView):
    """List all AIAnalysis results, filterable by run/priority."""
    model = AIAnalysis
    template_name = 'threat_intel_analysis_list.html'
    paginate_by = 50
    context_object_name = 'analyses'

    def get_queryset(self):
        qs = AIAnalysis.objects.select_related('item', 'run').order_by('-created_at')
        
        # Filtrar por run
        run_pk = self.request.GET.get('run_pk')
        if run_pk:
            qs = qs.filter(run__pk=run_pk)
        
        # Filtrar por prioridad
        priority = self.request.GET.get('priority')
        if priority:
            qs = qs.filter(priority=priority)
        
        # Filtrar por CVE/canonical_id
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(item__canonical_id__icontains=search)
        
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_pk = self.request.GET.get('run_pk')
        if run_pk:
            context['run'] = get_object_or_404(Run, pk=run_pk)
            context['back_url'] = reverse('threat_intel:run-detail', args=[run_pk])
        else:
            context['back_url'] = reverse('threat_intel:run-list')
        return context


class AIAnalysisDetailView(LoginRequiredMixin, DetailView):
    """Detail view for AIAnalysis with raw JSON display."""
    model = AIAnalysis
    template_name = 'threat_intel_analysis_detail.html'
    context_object_name = 'analysis'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        analysis = self.get_object()
        
        # Build display fields from model
        display_fields = [
            ('summary_es', 'Resumen', analysis.summary_es),
            ('impact_previ', 'Impacto Preliminar', analysis.impact_previ),
            ('recommended_action', 'Acciones Recomendadas', analysis.recommended_action),
            ('affected_tech', 'Tecnologías Afectadas', analysis.affected_tech),
            ('recommended_deadline', 'Deadline Recomendado', analysis.recommended_deadline),
            ('priority', 'Prioridad', analysis.priority),
            ('requires_management', 'Requiere Gestión', analysis.requires_management),
            ('notes', 'Notas', analysis.notes),
            ('model_name', 'Modelo IA', analysis.model_name),
            ('prompt_version', 'Versión de Prompt', analysis.prompt_version),
        ]
        
        context['display_fields'] = display_fields
        context['back_url'] = reverse('threat_intel:analysis-list') + f'?run_pk={analysis.run.pk}'
        context['rerun_url'] = reverse('threat_intel:analysis-rerun', args=[analysis.pk])
        context['export_url'] = reverse('threat_intel:analysis-export', args=[analysis.pk])
        context['item'] = analysis.item
        context['run'] = analysis.run
        return context


class AIAnalysisRerunView(LoginRequiredMixin, View):
    """Re-run analysis for a single item in a run."""
    def post(self, request, pk):
        analysis = get_object_or_404(AIAnalysis, pk=pk)
        item = analysis.item
        run = analysis.run
        
        try:
            from .services.ai import analyze_item, _normalize_ai_response, get_openai_api_client
            
            client = get_openai_api_client()
            model_name = client.model
            
            # Re-analyze
            data = analyze_item(client, item, model_name=model_name, prompt_version=analysis.prompt_version)
            
            # Update existing AIAnalysis
            def _as_text(v):
                if v is None:
                    return ""
                if isinstance(v, (list, tuple)):
                    return "\n".join(map(str, v))
                return str(v)
            
            analysis.summary_es = _as_text(data.get("summary_es", ""))
            analysis.applies_to_stack = bool(data.get("applies_to_stack", False))
            analysis.affected_tech = data.get("affected_tech", []) or []
            analysis.impact_previ = _as_text(data.get("impact_previ", ""))
            analysis.recommended_action = _as_text(data.get("recommended_action", ""))
            analysis.recommended_deadline = _as_text(data.get("recommended_deadline", ""))[:60]
            analysis.priority = (data.get("priority") or "medium").lower()[:20]
            analysis.requires_management = bool(data.get("requires_management", False))
            analysis.notes = _as_text(data.get("notes", ""))
            analysis.save()
            
            messages.success(request, f'Análisis re-ejecutado para {item.canonical_id}')
        except Exception as e:
            messages.error(request, f'Error al re-analizar: {e}')
        
        return redirect('threat_intel:analysis-detail', pk=pk)


class AIAnalysisExportView(LoginRequiredMixin, View):
    """Export AIAnalysis as JSON."""
    def get(self, request, pk):
        analysis = get_object_or_404(AIAnalysis, pk=pk)
        
        data = {
            'id': analysis.id,
            'item': {
                'canonical_id': analysis.item.canonical_id,
                'title': analysis.item.title,
                'severity': analysis.item.severity,
                'cvss': float(analysis.item.cvss) if analysis.item.cvss else None,
            },
            'run': {
                'id': analysis.run.id,
                'period_start': analysis.run.period_start.isoformat(),
                'period_end': analysis.run.period_end.isoformat(),
            },
            'analysis': {
                'summary_es': analysis.summary_es,
                'impact_previ': analysis.impact_previ,
                'recommended_action': analysis.recommended_action,
                'affected_tech': analysis.affected_tech,
                'recommended_deadline': analysis.recommended_deadline,
                'priority': analysis.priority,
                'requires_management': analysis.requires_management,
                'applies_to_stack': analysis.applies_to_stack,
                'notes': analysis.notes,
                'model_name': analysis.model_name,
                'prompt_version': analysis.prompt_version,
                'created_at': analysis.created_at.isoformat(),
            }
        }
        
        resp = HttpResponse(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="analysis_{analysis.pk}_{analysis.item.canonical_id}.json"'
        return resp


class ReportListView(LoginRequiredMixin, ListView):
    """List all reports for a tenant."""
    model = Report
    template_name = 'threat_intel_report_list.html'
    paginate_by = 20
    context_object_name = 'reports'

    def get_queryset(self):
        return Report.objects.select_related('run').order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('threat_intel:run-list')
        return context


class ReportDetailView(LoginRequiredMixin, DetailView):
    """View/preview a report (HTML or Markdown)."""
    model = Report
    template_name = 'threat_intel_report_detail.html'
    context_object_name = 'report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.get_object()
        
        # Get related analyses and reviews for context
        analyses = AIAnalysis.objects.filter(run=report.run).select_related('item')
        reviews = Review.objects.filter(run=report.run).select_related('item', 'decided_by')
        
        context['analyses'] = analyses
        context['reviews'] = reviews
        context['back_url'] = reverse('threat_intel:report-list')
        context['send_url'] = reverse('threat_intel:report-send', args=[report.pk])
        context['run_detail_url'] = reverse('threat_intel:run-detail', args=[report.run.pk])
        return context


class ReportCreateView(LoginRequiredMixin, CreateView):
    """Generate a report from a run."""
    model = Report
    template_name = 'threat_intel_report_create.html'
    fields = ['subject', 'body_md', 'recipients']

    def get_initial(self):
        run_pk = self.kwargs.get('run_pk')
        run = get_object_or_404(Run, pk=run_pk)
        
        # Auto-generate subject and body_md
        initial = {
            'subject': f'Threat Intel Report - Run #{run.pk} ({run.period_start.strftime("%Y-%m-%d")})',
            'body_md': f"""# Threat Intelligence Report

**Run:** {run.pk}
**Period:** {run.period_start.strftime('%Y-%m-%d')} to {run.period_end.strftime('%Y-%m-%d')}
**Status:** {run.status}
**Fetched Items:** {run.fetched_count}
**Normalized:** {run.normalized_count}
**Relevant:** {run.relevant_count}

## Summary

This report contains the threat intelligence analysis for the period above.

## Analyses

""",
        }
        
        # Add analyses summary
        analyses = AIAnalysis.objects.filter(run=run).select_related('item')
        for analysis in analyses[:10]:  # Limit to first 10
            initial['body_md'] += f"""
### {analysis.item.canonical_id} - {analysis.item.title}

**Severity:** {analysis.item.severity} | **CVSS:** {analysis.item.cvss or 'N/A'}
**Priority:** {analysis.priority}

{analysis.summary_es}
"""
        
        if analyses.count() > 10:
            initial['body_md'] += f"\n... and {analyses.count() - 10} more analyses\n"
        
        return initial

    def form_valid(self, form):
        run_pk = self.kwargs.get('run_pk')
        run = get_object_or_404(Run, pk=run_pk)
        form.instance.run = run
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_pk = self.kwargs.get('run_pk')
        context['run'] = get_object_or_404(Run, pk=run_pk)
        context['back_url'] = reverse('threat_intel:run-detail', args=[run_pk])
        return context

    def get_success_url(self):
        return reverse('threat_intel:report-detail', args=[self.object.pk])


class ReportSendView(LoginRequiredMixin, View):
    """Send report via email with PDF attachment."""
    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        
        # Get send parameters from POST data
        send_email = request.POST.get('send_email', False) == 'on'
        include_pdf = request.POST.get('include_pdf', False) == 'on'
        use_brevo = request.POST.get('use_brevo', False) == 'on'
        
        attachments = []
        
        # Generate PDF if requested
        if include_pdf:
            try:
                filename, pdf_content = generate_report_pdf(report)
                attachments.append((filename, pdf_content, "application/pdf"))
                messages.info(request, f'PDF generado: {filename}')
            except ImportError:
                messages.warning(request, 'WeasyPrint no instalado. Instala con: pip install weasyprint')
            except Exception as e:
                messages.warning(request, f'Error generando PDF: {str(e)}')
        
        # Send email if requested
        if send_email:
            result = send_report_email(report, attachments=attachments, use_brevo=use_brevo)
            
            if result['status'] == 'success':
                report.sent_at = timezone.now()
                report.save()
                backend = "Brevo" if use_brevo else "SMTP"
                messages.success(
                    request, 
                    f"✓ Reporte enviado vía {backend} a {len(report.recipients or [])} destinatarios"
                )
            else:
                messages.error(request, f"Error enviando email: {result['message']}")
        else:
            # Mark as sent even without email
            report.sent_at = timezone.now()
            report.save()
            messages.success(request, 'Reporte marcado como enviado')
        
        return redirect('threat_intel:report-detail', pk=pk)


class ReviewCreateView(LoginRequiredMixin, CreateView):
    """Create a review/decision for an item in a run."""
    model = Review
    template_name = 'threat_intel_review_create.html'
    fields = ['decision', 'notes', 'ticket_ref']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_pk = self.kwargs.get('run_pk')
        item_pk = self.kwargs.get('item_pk')
        
        context['run'] = get_object_or_404(Run, pk=run_pk)
        context['item'] = get_object_or_404(IntelItem, pk=item_pk)
        context['analysis'] = AIAnalysis.objects.filter(item_id=item_pk, run_id=run_pk).first()
        context['back_url'] = reverse('threat_intel:runitem-list', args=[run_pk])
        return context

    def form_valid(self, form):
        run_pk = self.kwargs.get('run_pk')
        item_pk = self.kwargs.get('item_pk')
        
        run = get_object_or_404(Run, pk=run_pk)
        item = get_object_or_404(IntelItem, pk=item_pk)
        
        form.instance.run = run
        form.instance.item = item
        form.instance.decided_by = self.request.user
        form.instance.analysis = AIAnalysis.objects.filter(item=item, run=run).first()
        
        return super().form_valid(form)

    def get_success_url(self):
        run_pk = self.kwargs.get('run_pk')
        return reverse('threat_intel:runitem-list', args=[run_pk])


class ReviewListView(LoginRequiredMixin, ListView):
    """List reviews for a run or globally."""
    model = Review
    template_name = 'threat_intel_review_list.html'
    paginate_by = 50
    context_object_name = 'reviews'

    def get_queryset(self):
        run_pk = self.kwargs.get('run_pk')
        if run_pk:
            qs = Review.objects.filter(run__pk=run_pk)
        else:
            qs = Review.objects.all()
        
        return qs.select_related('item', 'run', 'decided_by').order_by('-decided_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_pk = self.kwargs.get('run_pk')
        if run_pk:
            context['run'] = get_object_or_404(Run, pk=run_pk)
            context['back_url'] = reverse('threat_intel:run-detail', args=[run_pk])
        else:
            context['back_url'] = reverse('threat_intel:run-list')
        return context


class ReviewDetailView(LoginRequiredMixin, DetailView):
    """View a review/decision."""
    model = Review
    template_name = 'threat_intel_review_detail.html'
    context_object_name = 'review'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        review = self.get_object()
        context['back_url'] = reverse('threat_intel:review-list-run', args=[review.run.pk])
        context['edit_url'] = reverse('threat_intel:review-update', args=[review.pk])
        return context


class ReviewUpdateView(LoginRequiredMixin, UpdateView):
    """Edit a review/decision."""
    model = Review
    template_name = 'threat_intel_review_update.html'
    fields = ['decision', 'notes', 'ticket_ref']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        review = self.get_object()
        context['back_url'] = reverse('threat_intel:review-detail', args=[review.pk])
        context['item'] = review.item
        context['run'] = review.run
        return context

    def get_success_url(self):
        return reverse('threat_intel:review-detail', args=[self.object.pk])


# Configuration Views
class SourceListView(LoginRequiredMixin, ListView):
    """List all data sources with status indicators."""
    model = Source
    template_name = 'threat_intel_source_list.html'
    context_object_name = 'sources'
    paginate_by = 20

    def get_queryset(self):
        return Source.objects.all().order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('threat_intel:config')
        return context


class SourceDetailView(LoginRequiredMixin, DetailView):
    """View source details with editing options."""
    model = Source
    template_name = 'threat_intel_source_detail.html'
    context_object_name = 'source'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self.get_object()
        context['back_url'] = reverse('threat_intel:source-list')
        context['edit_url'] = reverse('threat_intel:source-update', args=[source.pk])
        return context


class SourceCreateView(LoginRequiredMixin, CreateView):
    """Create a new data source."""
    model = Source
    template_name = 'threat_intel_source_create.html'
    fields = ['code', 'name', 'kind', 'base_url', 'is_active']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('threat_intel:source-list')
        return context

    def get_success_url(self):
        return reverse('threat_intel:source-detail', args=[self.object.pk])


class SourceUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing data source."""
    model = Source
    template_name = 'threat_intel_source_update.html'
    fields = ['code', 'name', 'kind', 'base_url', 'is_active']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source = self.get_object()
        context['back_url'] = reverse('threat_intel:source-detail', args=[source.pk])
        return context

    def get_success_url(self):
        messages.success(self.request, f"Fuente '{self.object.name}' actualizada correctamente.")
        return reverse('threat_intel:source-detail', args=[self.object.pk])


class TechTagListView(LoginRequiredMixin, ListView):
    """List all technology tags with active status."""
    model = TechTag
    template_name = 'threat_intel_techtag_list.html'
    context_object_name = 'techtags'
    paginate_by = 20

    def get_queryset(self):
        queryset = TechTag.objects.all().order_by('name')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(keywords__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('threat_intel:config')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class TechTagDetailView(LoginRequiredMixin, DetailView):
    """View technology tag details with keywords."""
    model = TechTag
    template_name = 'threat_intel_techtag_detail.html'
    context_object_name = 'techtag'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        techtag = self.get_object()
        context['back_url'] = reverse('threat_intel:techtag-list')
        context['edit_url'] = reverse('threat_intel:techtag-update', args=[techtag.pk])
        return context


class TechTagCreateView(LoginRequiredMixin, CreateView):
    """Create a new technology tag."""
    model = TechTag
    template_name = 'threat_intel_techtag_create.html'
    fields = ['name', 'keywords', 'is_active']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('threat_intel:techtag-list')
        return context

    def get_success_url(self):
        messages.success(self.request, f"Etiqueta '{self.object.name}' creada correctamente.")
        return reverse('threat_intel:techtag-detail', args=[self.object.pk])


class TechTagUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing technology tag."""
    model = TechTag
    template_name = 'threat_intel_techtag_update.html'
    fields = ['name', 'keywords', 'is_active']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        techtag = self.get_object()
        context['back_url'] = reverse('threat_intel:techtag-detail', args=[techtag.pk])
        return context

    def get_success_url(self):
        messages.success(self.request, f"Etiqueta '{self.object.name}' actualizada correctamente.")
        return reverse('threat_intel:techtag-detail', args=[self.object.pk])


class ConfigView(LoginRequiredMixin, ListView):
    """Configuration overview for threat intelligence."""
    model = Source
    template_name = 'threat_intel_config.html'
    context_object_name = 'sources'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['techtag_count'] = TechTag.objects.count()
        context['source_count'] = Source.objects.count()
        context['active_sources'] = Source.objects.filter(is_active=True).count()
        context['active_techtags'] = TechTag.objects.filter(is_active=True).count()
        return context
