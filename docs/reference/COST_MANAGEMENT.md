# Cost Management and Budget Control

> ## ⚠️ Status: Phase 1+ design — not yet implemented
>
> **Что реализовано сегодня (Phase 0):** только token-budget enforcement через
> `LLMConfig.max_tokens_per_run` (default 30 000). При превышении гейтвей
> выбрасывает `TokenBudgetExceeded` (см.
> [`gateway.py:394-407`](../../digest-core/src/digest_core/llm/gateway.py)).
>
> **Что НЕ реализовано** (всё описанное ниже):
> - 🔴 `cost_limit_per_run` enforcement (TD-006 в `ARCHITECTURE.md §13.2` open)
> - 🔴 Per-user / per-organization daily/monthly/yearly cost limits
> - 🔴 `CostOptimizer` класс, fallback strategies, automatic optimization
> - 🔴 Cost-related Prometheus метрики (`cost_per_digest_usd`, `budget_utilization_percent`,
>   `cost_optimization_events_total`)
> - 🔴 Cost reporting / алерты по стоимости
>
> Для проверки текущих лимитов смотрите ARCHITECTURE.md §5.1 (`LLMConfig`)
> и §6.1 (instrumented Prometheus метрики).
>
> Этот документ описывает желаемое состояние Phase 1+, не текущее.
> Связанная задача: ACTPULSE-41 (закрыт, alignment не завершён) и
> [TD-006](../../digest-core/docs/ARCHITECTURE.md).

Управление стоимостью и контроль бюджета для ActionPulse.

## Обзор системы управления стоимостью

### Принципы управления стоимостью

- **Predictable Costs:** предсказуемые расходы с лимитами
- **Cost Optimization:** автоматическая оптимизация при превышении
- **Transparent Billing:** прозрачная отчётность по расходам
- **Graceful Degradation:** снижение качества при превышении бюджета

### Компоненты системы

1. **Budget Limits** - лимиты на пользователя/день/месяц
2. **Cost Monitoring** - мониторинг расходов в реальном времени
3. **Automatic Optimization** - автоматическая оптимизация
4. **Fallback Strategies** - стратегии снижения качества
5. **Cost Reporting** - отчётность и аналитика

## Бюджетные лимиты

### Пользовательские лимиты

```yaml
cost_limits:
  per_user:
    daily: 0.50    # USD per day per user
    monthly: 10.00 # USD per month per user
    yearly: 100.00 # USD per year per user
  
  per_organization:
    daily: 50.00   # USD per day for organization
    monthly: 1000.00 # USD per month for organization
  
  per_digest:
    max: 0.10      # USD per digest generation
    warning: 0.08  # USD warning threshold
```

### Лимиты по компонентам

```yaml
component_limits:
  llm:
    tokens_per_run: 30000
    cost_per_1k_tokens: 0.002
    max_retries: 3
  
  ews:
    api_calls_per_hour: 1000
    cost_per_call: 0.001
  
  storage:
    retention_days: 7
    cost_per_gb_month: 0.023
```

## Мониторинг стоимости

### Метрики в реальном времени

```python
# Prometheus метрики
cost_metrics = {
    'llm_cost_usd_total': 'Общая стоимость LLM запросов',
    'llm_tokens_in_total': 'Входящие токены',
    'llm_tokens_out_total': 'Исходящие токены',
    'cost_per_digest_usd': 'Стоимость за дайджест',
    'cost_per_user_daily_usd': 'Стоимость пользователя в день',
    'budget_utilization_percent': 'Использование бюджета',
    'cost_optimization_events_total': 'События оптимизации'
}
```

### Алерты по стоимости

```yaml
cost_alerts:
  critical:
    - condition: "cost_per_user_daily_usd > 0.50"
      message: "Daily budget exceeded for user"
      action: "disable_user_digests"
    
    - condition: "cost_per_digest_usd > 0.10"
      message: "Digest cost too high"
      action: "trigger_optimization"
  
  warning:
    - condition: "budget_utilization_percent > 80"
      message: "Budget utilization high"
      action: "send_notification"
    
    - condition: "cost_per_digest_usd > 0.08"
      message: "Digest cost approaching limit"
      action: "log_warning"
```

## Стратегии оптимизации

### Автоматическая оптимизация

```python
class CostOptimizer:
    def __init__(self, budget_limits: Dict, current_costs: Dict):
        self.budget_limits = budget_limits
        self.current_costs = current_costs
    
    def optimize_digest_generation(self, user_id: str, digest_config: Dict) -> Dict:
        """Optimize digest generation to stay within budget."""
        
        user_daily_cost = self.current_costs.get(f"user_{user_id}_daily", 0)
        remaining_budget = self.budget_limits["per_user"]["daily"] - user_daily_cost
        
        if remaining_budget < 0.01:  # Less than 1 cent
            return self.create_fallback_config()
        
        # Optimize based on remaining budget
        if remaining_budget < 0.05:
            return self.create_low_budget_config(digest_config)
        elif remaining_budget < 0.08:
            return self.create_medium_budget_config(digest_config)
        else:
            return digest_config
    
    def create_fallback_config(self) -> Dict:
        """Create fallback configuration for zero budget."""
        return {
            "llm_enabled": False,
            "extraction_mode": "rule_based",
            "max_evidence_spans": 5,
            "max_tokens": 1000,
            "quality_level": "basic"
        }
    
    def create_low_budget_config(self, base_config: Dict) -> Dict:
        """Create low budget configuration."""
        return {
            **base_config,
            "max_tokens": 15000,
            "max_evidence_spans": 8,
            "llm_temperature": 0.0,  # More deterministic
            "quality_level": "standard"
        }
    
    def create_medium_budget_config(self, base_config: Dict) -> Dict:
        """Create medium budget configuration."""
        return {
            **base_config,
            "max_tokens": 25000,
            "max_evidence_spans": 12,
            "quality_level": "high"
        }
```

### Стратегии снижения качества

#### Уровень 1: Оптимизация токенов

```python
def optimize_token_usage(evidence_texts: List[str], max_tokens: int) -> List[str]:
    """Optimize evidence texts to fit within token limit."""
    
    # Sort by importance score
    sorted_evidence = sorted(evidence_texts, key=lambda x: x['importance'], reverse=True)
    
    total_tokens = 0
    selected_evidence = []
    
    for evidence in sorted_evidence:
        tokens = estimate_tokens(evidence['text'])
        if total_tokens + tokens <= max_tokens:
            selected_evidence.append(evidence)
            total_tokens += tokens
        else:
            break
    
    return selected_evidence
```

#### Уровень 2: Отключение эмбеддингов

```python
def disable_embeddings_config(config: Dict) -> Dict:
    """Disable expensive embedding operations."""
    return {
        **config,
        "use_embeddings": False,
        "context_selection": "rule_based",
        "semantic_clustering": False
    }
```

#### Уровень 3: Только экстрактивное резюме

```python
def extractive_only_config(config: Dict) -> Dict:
    """Switch to extractive summarization only."""
    return {
        **config,
        "llm_enabled": False,
        "summarization_mode": "extractive",
        "use_keyword_extraction": True,
        "use_sentence_ranking": True
    }
```

## Фолбэки при превышении бюджета

### Матрица деградации

| Ситуация | Политика | Действия |
|----------|----------|----------|
| LLM недоступен / таймаут | Экстрактивное резюме | BM25+правила, без генерации |
| Превышен cost-budget/user/day | Снижаем контекст | Отключаем эмбеддинги, только экстрактив |
| EWS/MM недоступен | Частичный отчёт | По доступным источникам с баннером «неполный» |
| Большой объём | Батчинг | Кэш эмбеддингов, сплит на сообщения |

### Реализация фолбэков

```python
class FallbackManager:
    def __init__(self, cost_monitor, quality_monitor):
        self.cost_monitor = cost_monitor
        self.quality_monitor = quality_monitor
    
    def handle_budget_exceeded(self, user_id: str) -> FallbackStrategy:
        """Handle budget exceeded situation."""
        
        # Check current usage
        daily_usage = self.cost_monitor.get_daily_usage(user_id)
        monthly_usage = self.cost_monitor.get_monthly_usage(user_id)
        
        if daily_usage > self.budget_limits["per_user"]["daily"]:
            return FallbackStrategy.EXTRACTIVE_ONLY
        
        if monthly_usage > self.budget_limits["per_user"]["monthly"] * 0.9:
            return FallbackStrategy.REDUCED_QUALITY
        
        return FallbackStrategy.NORMAL
    
    def apply_fallback_strategy(self, strategy: FallbackStrategy, config: Dict) -> Dict:
        """Apply fallback strategy to configuration."""
        
        if strategy == FallbackStrategy.EXTRACTIVE_ONLY:
            return self.create_extractive_config(config)
        elif strategy == FallbackStrategy.REDUCED_QUALITY:
            return self.create_reduced_quality_config(config)
        else:
            return config
```

## Отчётность по стоимости

### Ежедневные отчёты

```python
def generate_daily_cost_report(date: str) -> Dict:
    """Generate daily cost report."""
    
    report = {
        "date": date,
        "total_cost": 0,
        "by_user": {},
        "by_component": {
            "llm": 0,
            "ews": 0,
            "storage": 0
        },
        "optimization_events": [],
        "budget_alerts": []
    }
    
    # Aggregate costs by user
    for user_id in get_active_users(date):
        user_cost = calculate_user_daily_cost(user_id, date)
        report["by_user"][user_id] = user_cost
        report["total_cost"] += user_cost
    
    # Aggregate costs by component
    report["by_component"]["llm"] = calculate_llm_cost(date)
    report["by_component"]["ews"] = calculate_ews_cost(date)
    report["by_component"]["storage"] = calculate_storage_cost(date)
    
    # Add optimization events
    report["optimization_events"] = get_optimization_events(date)
    
    # Add budget alerts
    report["budget_alerts"] = get_budget_alerts(date)
    
    return report
```

### Еженедельные аналитические отчёты

```python
def generate_weekly_cost_analysis(start_date: str, end_date: str) -> Dict:
    """Generate weekly cost analysis report."""
    
    analysis = {
        "period": f"{start_date} to {end_date}",
        "total_cost": 0,
        "cost_trends": {},
        "optimization_impact": {},
        "budget_utilization": {},
        "recommendations": []
    }
    
    # Calculate cost trends
    daily_costs = [calculate_daily_cost(date) for date in date_range(start_date, end_date)]
    analysis["cost_trends"] = {
        "average_daily": sum(daily_costs) / len(daily_costs),
        "trend": calculate_trend(daily_costs),
        "volatility": calculate_volatility(daily_costs)
    }
    
    # Calculate optimization impact
    analysis["optimization_impact"] = {
        "cost_savings": calculate_cost_savings(start_date, end_date),
        "quality_impact": calculate_quality_impact(start_date, end_date),
        "user_satisfaction_impact": calculate_satisfaction_impact(start_date, end_date)
    }
    
    # Generate recommendations
    analysis["recommendations"] = generate_cost_recommendations(analysis)
    
    return analysis
```

## Инструменты мониторинга

### Prometheus метрики

```promql
# Основные метрики стоимости
llm_cost_usd_total
cost_per_digest_usd
cost_per_user_daily_usd
budget_utilization_percent

# Метрики оптимизации
cost_optimization_events_total{strategy}
token_usage_efficiency
cache_hit_rate

# Алерты
cost_budget_exceeded_total
cost_optimization_triggered_total
```

### Grafana дашборды

- **Cost Overview** - общий обзор расходов
- **User Cost Analysis** - анализ расходов по пользователям
- **Component Cost Breakdown** - разбивка по компонентам
- **Optimization Impact** - влияние оптимизаций
- **Budget Utilization** - использование бюджета

### Алерты и уведомления

```yaml
cost_alerts:
  - name: "Daily Budget Exceeded"
    condition: "cost_per_user_daily_usd > 0.50"
    severity: "critical"
    channels: ["pagerduty", "slack"]
  
  - name: "High Digest Cost"
    condition: "cost_per_digest_usd > 0.08"
    severity: "warning"
    channels: ["slack"]
  
  - name: "Budget Utilization High"
    condition: "budget_utilization_percent > 80"
    severity: "warning"
    channels: ["email"]
```

## Рекомендации по оптимизации

### Краткосрочные (1-2 недели)

1. **Кэширование эмбеддингов** - снижение стоимости на 30-40%
2. **Оптимизация промптов** - снижение токенов на 20-30%
3. **Батчинг запросов** - снижение overhead на 15-25%
4. **Настройка лимитов** - предотвращение превышений

### Среднесрочные (1-2 месяца)

1. **Внедрение локальных моделей** - снижение стоимости на 50-70%
2. **Оптимизация архитектуры** - снижение ресурсов на 20-30%
3. **Улучшение алгоритмов отбора** - снижение токенов на 25-35%
4. **Автоматическое масштабирование** - оптимизация ресурсов

### Долгосрочные (3-6 месяцев)

1. **Собственная LLM инфраструктура** - контроль стоимости
2. **Продвинутые техники сжатия** - снижение токенов на 40-60%
3. **Машинное обучение для оптимизации** - автоматическая настройка
4. **Предиктивная аналитика** - предсказание расходов

---

**Итог:** Эта система управления стоимостью обеспечивает контроль расходов, автоматическую оптимизацию и прозрачную отчётность, позволяя поддерживать качество сервиса в рамках бюджета.
