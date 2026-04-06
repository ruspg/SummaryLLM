# Quality Metrics and AI Evaluation

> ## ⚠️ Status: Phase 1+ design — gold-set evaluation не реализован
>
> Этот документ описывает **запланированную** систему оценки качества (gold-сеты,
> разметка, P/R/F1, regression-гейтинг). Сегодня в коде ничего из этого нет.
>
> **Что есть сегодня (Phase 0):**
>
> - Pydantic-валидация LLM output на каждом запуске (см.
>   [`llm/schemas.py`](../../digest-core/src/digest_core/llm/schemas.py))
> - Citation validation через `--validate-citations` (exit code 2 при failures)
> - Counter-метрики (не quality scores): `actions_found_total`, `mentions_found_total`,
>   `actions_confidence_histogram`, `citation_validation_failures_total`
> - Quality retry на пустые секции при наличии positive evidence (см. ADR-008)
>
> **Что НЕ реализовано** (всё описанное ниже):
>
> - 🔴 Gold-сеты, разметка, inter-annotator agreement
> - 🔴 P/R/F1, exact-match, partial-match, hallucination_rate как метрики
> - 🔴 Regression-гейтинг по качеству (CI блокирует merge при падении метрик)
> - 🔴 Brier Score (калибровка confidence)
> - 🔴 A/B-тестирование промптов
>
> Документ ведётся как target spec для Phase 1+. До тех пор канонический список
> инструментированных метрик —
> [`metrics.py`](../../digest-core/src/digest_core/observability/metrics.py) и
> [`ARCHITECTURE.md §6.1`](../../digest-core/docs/ARCHITECTURE.md).

Метрики качества AI и система оценки эффективности ActionPulse.

## Обзор системы качества

### Принципы оценки

- **Extract-over-Generate:** приоритет извлечения над генерацией
- **Evidence-based:** каждый вывод должен иметь основание
- **Reproducible:** результаты должны быть воспроизводимыми
- **Measurable:** все метрики должны быть количественными

### Компоненты системы качества

1. **Gold-сеты и разметка**
2. **Метрики извлечения**
3. **Метрики генерации**
4. **Метрики трассируемости**
5. **Regression-гейтинг**

## Gold-сеты и разметка

### Структура gold-сетов

```json
{
  "dataset_id": "gold-v1.0",
  "created_at": "2024-01-15T10:00:00Z",
  "annotators": ["annotator1", "annotator2"],
  "inter_annotator_agreement": 0.85,
  "samples": [
    {
      "sample_id": "sample-001",
      "source": "email",
      "language": "ru",
      "content": "Пожалуйста, утвердите бюджет Q3 до пятницы.",
      "annotations": {
        "action_items": [
          {
            "type": "approval",
            "owner": "recipient",
            "due": "2024-01-19",
            "confidence": 0.95,
            "evidence_span": [0, 45]
          }
        ],
        "mentions": [
          {
            "type": "direct_request",
            "target": "recipient",
            "confidence": 0.90,
            "evidence_span": [0, 15]
          }
        ]
      }
    }
  ]
}
```

### Критерии разметки

#### Action Items

- **Тип действия:** approval, review, decision, deadline, information
- **Владелец:** конкретное лицо или роль
- **Срок:** явный или неявный дедлайн
- **Приоритет:** high, medium, low
- **Контекст:** достаточный для понимания

#### Mentions

- **Тип упоминания:** direct_request, cc_notification, approval_needed
- **Целевое лицо:** конкретный получатель
- **Явность:** explicit, implicit, inferred
- **Контекст:** достаточный для идентификации

### Инструкции разметчикам

#### Общие принципы

1. **Консервативность:** лучше пропустить, чем ошибиться
2. **Консистентность:** одинаковые случаи размечать одинаково
3. **Контекстность:** учитывать полный контекст сообщения
4. **Практичность:** фокус на практически значимых элементах

#### Специфические правила

**Action Items:**
- Включать только действия, требующие конкретного ответа
- Исключать общие призывы к действию без конкретики
- Учитывать иерархию и роли участников
- Различать запросы и уведомления

**Mentions:**
- Включать только релевантные упоминания
- Исключать формальные обращения в подписях
- Учитывать контекст получателей (To vs CC)
- Различать личные и групповые обращения

### Межразметочное согласие

- **Цель:** κ ≥ 0.7 (Cohen's Kappa)
- **Метрика:** согласие по всем категориям
- **Процесс:** двойная разметка 20% выборки
- **Разрешение конфликтов:** консенсус или экспертное решение

## Метрики извлечения

### Mentions Detection

#### Precision/Recall/F1

```python
def calculate_mentions_metrics(predictions, gold_standard):
    """Calculate mentions detection metrics."""
    
    # Exact match: same type, target, and span
    exact_matches = 0
    for pred in predictions:
        for gold in gold_standard:
            if (pred['type'] == gold['type'] and 
                pred['target'] == gold['target'] and
                pred['span'] == gold['span']):
                exact_matches += 1
                break
    
    precision = exact_matches / len(predictions) if predictions else 0
    recall = exact_matches / len(gold_standard) if gold_standard else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'exact_matches': exact_matches
    }
```

#### Brier Score (калибровка)

```python
def calculate_brier_score(predictions, gold_standard):
    """Calculate Brier score for confidence calibration."""
    
    brier_scores = []
    for pred in predictions:
        # Find matching gold standard
        is_correct = any(
            pred['type'] == gold['type'] and pred['target'] == gold['target']
            for gold in gold_standard
        )
        
        # Brier score: (predicted_prob - actual_outcome)^2
        brier_score = (pred['confidence'] - (1 if is_correct else 0)) ** 2
        brier_scores.append(brier_score)
    
    return sum(brier_scores) / len(brier_scores) if brier_scores else 0
```

#### Citation Accuracy

```python
def calculate_citation_accuracy(predictions, gold_standard):
    """Calculate accuracy of evidence citations."""
    
    correct_citations = 0
    total_citations = 0
    
    for pred in predictions:
        if 'evidence_span' in pred:
            total_citations += 1
            
            # Find matching gold standard
            for gold in gold_standard:
                if (pred['type'] == gold['type'] and 
                    pred['target'] == gold['target']):
                    
                    # Check if citation is correct (within 10% overlap)
                    pred_span = pred['evidence_span']
                    gold_span = gold['evidence_span']
                    
                    overlap = calculate_span_overlap(pred_span, gold_span)
                    if overlap >= 0.1:  # 10% overlap threshold
                        correct_citations += 1
                    break
    
    return correct_citations / total_citations if total_citations > 0 else 0
```

### Action Items Extraction

#### Exact Match

```python
def calculate_action_exact_match(predictions, gold_standard):
    """Calculate exact match for action items."""
    
    exact_matches = 0
    for pred in predictions:
        for gold in gold_standard:
            if (pred['type'] == gold['type'] and
                pred['owner'] == gold['owner'] and
                pred['due'] == gold['due']):
                exact_matches += 1
                break
    
    return exact_matches / len(gold_standard) if gold_standard else 0
```

#### Partial Match

```python
def calculate_action_partial_match(predictions, gold_standard):
    """Calculate partial match for action items."""
    
    partial_matches = 0
    for pred in predictions:
        for gold in gold_standard:
            # Match on type and owner (due date can differ)
            if (pred['type'] == gold['type'] and
                pred['owner'] == gold['owner']):
                partial_matches += 1
                break
    
    return partial_matches / len(gold_standard) if gold_standard else 0
```

## Метрики генерации

### Coverage значимых событий

```python
def calculate_coverage(predictions, gold_standard):
    """Calculate coverage of significant events."""
    
    # Identify significant events in gold standard
    significant_events = [
        event for event in gold_standard 
        if event['importance'] >= 0.7
    ]
    
    # Count how many were found
    found_significant = 0
    for event in significant_events:
        if any(
            pred['type'] == event['type'] and pred['target'] == event['target']
            for pred in predictions
        ):
            found_significant += 1
    
    return found_significant / len(significant_events) if significant_events else 0
```

### Hallucination Detection

```python
def calculate_hallucination_rate(predictions, source_texts):
    """Calculate rate of predictions without evidence."""
    
    hallucinated = 0
    for pred in predictions:
        if 'evidence_span' not in pred or not pred['evidence_span']:
            hallucinated += 1
        else:
            # Check if evidence span is valid
            span = pred['evidence_span']
            if span[0] < 0 or span[1] > len(source_texts[pred['source_id']]):
                hallucinated += 1
    
    return hallucinated / len(predictions) if predictions else 0
```

### Faithfulness (семантическая близость)

```python
def calculate_faithfulness(predictions, source_texts, embeddings_model):
    """Calculate semantic faithfulness of predictions to source."""
    
    faithfulness_scores = []
    
    for pred in predictions:
        if 'evidence_span' not in pred:
            faithfulness_scores.append(0.0)
            continue
        
        # Extract evidence text
        source_text = source_texts[pred['source_id']]
        evidence_text = source_text[pred['evidence_span'][0]:pred['evidence_span'][1]]
        
        # Generate embeddings
        evidence_embedding = embeddings_model.encode(evidence_text)
        prediction_embedding = embeddings_model.encode(pred['summary'])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(evidence_embedding, prediction_embedding)
        faithfulness_scores.append(similarity)
    
    return sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0
```

## Метрики трассируемости

### Citation Fidelity

```python
def calculate_citation_fidelity(predictions):
    """Calculate percentage of predictions with valid citations."""
    
    valid_citations = 0
    for pred in predictions:
        if ('evidence_id' in pred and 
            pred['evidence_id'] and
            'source_ref' in pred and
            pred['source_ref']):
            valid_citations += 1
    
    return valid_citations / len(predictions) if predictions else 0
```

### Trace Completeness

```python
def calculate_trace_completeness(predictions):
    """Calculate completeness of trace information."""
    
    required_fields = ['evidence_id', 'source_ref', 'confidence', 'trace_id']
    complete_traces = 0
    
    for pred in predictions:
        if all(field in pred and pred[field] for field in required_fields):
            complete_traces += 1
    
    return complete_traces / len(predictions) if predictions else 0
```

## Regression-гейтинг

### Quality Gate Process

```python
class QualityGate:
    def __init__(self, thresholds: Dict[str, float]):
        self.thresholds = thresholds
    
    def evaluate(self, predictions, gold_standard) -> QualityGateResult:
        """Evaluate predictions against quality gate thresholds."""
        
        results = {}
        
        # Calculate all metrics
        results['mentions_f1'] = calculate_mentions_metrics(predictions, gold_standard)['f1']
        results['action_exact_match'] = calculate_action_exact_match(predictions, gold_standard)
        results['coverage'] = calculate_coverage(predictions, gold_standard)
        results['citation_fidelity'] = calculate_citation_fidelity(predictions)
        results['hallucination_rate'] = calculate_hallucination_rate(predictions, source_texts)
        
        # Check thresholds
        passed = all(
            results[metric] >= threshold 
            for metric, threshold in self.thresholds.items()
        )
        
        return QualityGateResult(
            passed=passed,
            metrics=results,
            thresholds=self.thresholds
        )
```

### A/B Testing Framework

```python
class ABTestFramework:
    def __init__(self, control_model, treatment_model):
        self.control_model = control_model
        self.treatment_model = treatment_model
    
    def run_ab_test(self, test_data, gold_standard):
        """Run A/B test between two models."""
        
        # Run both models
        control_results = self.control_model.predict(test_data)
        treatment_results = self.treatment_model.predict(test_data)
        
        # Evaluate both
        control_metrics = self.evaluate_metrics(control_results, gold_standard)
        treatment_metrics = self.evaluate_metrics(treatment_results, gold_standard)
        
        # Statistical significance test
        significance = self.calculate_significance(control_metrics, treatment_metrics)
        
        return ABTestResult(
            control_metrics=control_metrics,
            treatment_metrics=treatment_metrics,
            significance=significance,
            recommendation=self.get_recommendation(control_metrics, treatment_metrics)
        )
```

## Целевые пороги

### MVP (Текущий)

| Метрика | Порог | Описание |
|---------|-------|----------|
| Mentions F1 | ≥ 0.75 | Базовая детекция упоминаний |
| Action Exact Match | ≥ 0.70 | Точное извлечение действий |
| Coverage | ≥ 0.85 | Покрытие значимых событий |
| Citation Fidelity | ≥ 0.90 | Валидные ссылки на источники |
| Hallucination Rate | ≤ 0.10 | Минимальные галлюцинации |

### LVL2 (Mentions)

| Метрика | Порог | Описание |
|---------|-------|----------|
| Mentions F1 | ≥ 0.82 | Улучшенная детекция |
| Mentions Precision | ≥ 0.85 | Высокая точность |
| Mentions Recall | ≥ 0.80 | Хорошая полнота |
| Brier Score | ≤ 0.15 | Калибровка уверенности |
| Citation Accuracy | ≥ 0.90 | Точные цитаты |

### LVL3+ (Advanced)

| Метрика | Порог | Описание |
|---------|-------|----------|
| Mentions F1 | ≥ 0.85 | Продвинутая детекция |
| Action Exact Match | ≥ 0.80 | Высокая точность действий |
| Coverage | ≥ 0.90 | Полное покрытие |
| Faithfulness | ≥ 0.85 | Семантическая близость |
| Trace Completeness | ≥ 0.95 | Полная трассируемость |

## Инструменты и автоматизация

### Continuous Quality Monitoring

```python
class QualityMonitor:
    def __init__(self, quality_gate: QualityGate):
        self.quality_gate = quality_gate
        self.metrics_history = []
    
    def monitor_batch(self, predictions, gold_standard):
        """Monitor quality of a batch of predictions."""
        
        result = self.quality_gate.evaluate(predictions, gold_standard)
        self.metrics_history.append(result)
        
        # Check for quality degradation
        if len(self.metrics_history) >= 5:
            recent_trend = self.analyze_trend()
            if recent_trend < -0.05:  # 5% degradation
                self.trigger_alert("Quality degradation detected")
        
        return result
    
    def analyze_trend(self):
        """Analyze quality trend over recent batches."""
        recent_metrics = self.metrics_history[-5:]
        return (recent_metrics[-1].overall_score - recent_metrics[0].overall_score) / 5
```

### Automated Quality Reports

```python
def generate_quality_report(metrics_history, time_period="daily"):
    """Generate automated quality report."""
    
    report = {
        "period": time_period,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_batches": len(metrics_history),
            "avg_quality_score": sum(m.overall_score for m in metrics_history) / len(metrics_history),
            "quality_gate_passes": sum(1 for m in metrics_history if m.passed)
        },
        "detailed_metrics": {
            metric: {
                "mean": statistics.mean(getattr(m, metric) for m in metrics_history),
                "std": statistics.stdev(getattr(m, metric) for m in metrics_history),
                "min": min(getattr(m, metric) for m in metrics_history),
                "max": max(getattr(m, metric) for m in metrics_history)
            }
            for metric in ["mentions_f1", "action_exact_match", "coverage", "citation_fidelity"]
        },
        "recommendations": generate_recommendations(metrics_history)
    }
    
    return report
```

---

**Итог:** Эта система метрик качества обеспечивает комплексную оценку эффективности ActionPulse на всех уровнях - от базового извлечения до продвинутой генерации и трассируемости.
