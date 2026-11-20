"""Budget-aware product selection from real candidate IDs only."""
from app.contracts import CuratorPlan, Pick, Skip, LLMMeta
from .nebius_client import ask, enabled, compact, model

def _eligible(candidates, cap):
    return {c: [p for p in ps if p.in_stock and 0 <= p.price_usd <= cap] for c, ps in candidates.items()}

def _fallback(candidates, budget, cap):
    remaining = budget
    picks, skipped = [], []
    for cat, products in _eligible(candidates, cap).items():
        affordable = [p for p in products if p.price_usd <= remaining]
        if affordable:
            p = sorted(affordable, key=lambda p: (-(p.score or 0), p.price_usd))[0]
            picks.append(Pick(category=cat, product_id=p.id, reason=f'Catalog match for {cat}; within budget'))
            remaining -= p.price_usd
        else:
            skipped.append(Skip(category=cat, reason='No eligible product within remaining budget'))
    return CuratorPlan(picks=picks, skipped=skipped, summary='Budget-aware catalog selection')

def curator(profile, memory, candidates, budget_usd: float, max_item_usd: float) -> CuratorPlan:
    fallback = _fallback(candidates, budget_usd, max_item_usd)
    if not enabled():
        fallback.meta = LLMMeta(model='mock', fallback_used=True)
        return fallback
    eligible = _eligible(candidates, max_item_usd)
    payload = {'task':'Choose at most one real product_id per category. Maximize room style coherence and stated preferences. Total selected prices <= budget. Never invent IDs. Output object {picks:[{category,product_id,reason}],skipped:[{category,reason}],summary}. Explain choices with actual listed attributes. No duplicate IDs.',
               'profile':profile.model_dump(exclude={'photo_url'}), 'memory':memory.model_dump(),
               'budget':budget_usd, 'max_item':max_item_usd,
               'candidates':{c:[{'id':p.id,'name':p.name,'price':p.price_usd,'colors':p.colors,'material':p.material,'style':p.style,'score':p.score} for p in ps[:4]] for c,ps in eligible.items()}}
    allowed = {c:{p.id:p for p in ps[:4]} for c,ps in eligible.items()}
    def validate(data):
        plan = CuratorPlan.model_validate(data)
        seen_categories, seen_ids, total = set(), set(), 0.0
        for pick in plan.picks:
            if pick.category in seen_categories or pick.product_id in seen_ids or pick.product_id not in allowed.get(pick.category, {}):
                raise ValueError('Invalid, duplicate or invented product ID')
            seen_categories.add(pick.category)
            seen_ids.add(pick.product_id)
            total += allowed[pick.category][pick.product_id].price_usd
        if total > budget_usd + 0.001:
            raise ValueError('Plan over budget')
        return plan
    try:
        plan, latency = ask('CURATOR', compact(payload), max_tokens=1400, validator=validate)
        plan.meta = LLMMeta(model=model('CURATOR'), latency_ms=latency, fallback_used=False)
        return plan
    except Exception:
        fallback.meta = LLMMeta(model=model('CURATOR'), fallback_used=True)
        return fallback
