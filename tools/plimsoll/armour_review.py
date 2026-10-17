"""Read-only empirical armour length/height checks; never changes a mass."""
import copy
import math

try:
    from . import concept_estimates as source
except ImportError:  # direct module imports
    import concept_estimates as source

METHOD_VERSION = 'sps-3b3-armour-review-v1'
SOURCE_LOCATION = 'ArmourControl.cs:628-690; MainForm.cs:1900-1919'


class ReviewValidationError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__('; '.join(d['message'] for d in diagnostics))


def validate_config(raw, path='$.concept_design.armour_review'):
    if raw is None:
        return None
    diagnostics = []
    def error(message, suffix=''):
        diagnostics.append(dict(code='armour_review.invalid', path=path + suffix,
                                message=message, severity='error', blocking=True))
    if not isinstance(raw, dict):
        error('armour review must be an object or null')
        raise ReviewValidationError(diagnostics)
    for key in set(raw) - {'source', 'belt_inclination_deg'}:
        error('unsupported field %r' % key, '.' + key)
    note = raw.get('source')
    if note is not None and not isinstance(note, str):
        error('source must be text or null', '.source')
    angle = raw.get('belt_inclination_deg')
    if angle is not None and (isinstance(angle, bool) or not isinstance(angle, (float, int))
                              or not -89 <= angle <= 89):
        error('inclination must be finite degrees in [-89, 89] or null', '.belt_inclination_deg')
    if diagnostics:
        raise ReviewValidationError(diagnostics)
    return {'source': note.strip() or None if isinstance(note, str) else None,
            'belt_inclination_deg': angle}


def _number(value):
    value = value.get('value') if isinstance(value, dict) else value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except (OverflowError, ValueError):
        return None


def evaluate(records, context, config, path='$.concept_design.armour_review'):
    """Independent checks with per-check availability, using selected screen facts."""
    facts = {name: _number(context.get(name)) for name in
             ('length_m', 'draught_m', 'freeboard_m', 'room_hull_ratio', 'composite_strength')}
    length, draft, free = (facts[k] for k in ('length_m', 'draught_m', 'freeboard_m'))
    angle = _number(config.get('belt_inclination_deg'))
    checks = []

    def add(identity, record_id, code, readable, warning=False, values=None):
        checks.append(dict(id=identity, record_id=record_id,
                           status=('warning' if warning else 'pass') if readable else 'unavailable',
                           code=code, values=values or {},
                           message=MESSAGES[code]))

    room, strength = facts['room_hull_ratio'], facts['composite_strength']
    minimum = None
    if (length is not None and length > 0 and room is not None and room >= 0
            and strength is not None and strength >= .5):
        candidate = length * .65 * room + .01 * .3048
        if math.isfinite(candidate):
            minimum = candidate
    add('minimum_length', None, 'minimum_length', minimum is not None,
        values={'minimum_main_belt_length_m': minimum})
    mains = [r for r in records if r.get('kind') == 'belt_main']
    ends = [r for r in records if r.get('kind') == 'belt_ends']
    pair_sum = None
    if len(mains) == len(ends) == 1:
        sizes = [_number(r.get('length_m')) for r in (mains[0], ends[0])]
        if all(n is not None and n >= 0 for n in sizes):
            pair_sum = sum(sizes)
    pair_known = pair_sum is not None and length is not None and length > 0
    add('belt_pair', None, 'belt_pair', pair_known,
        warning=pair_known and pair_sum > length,
        values={'declared_length_m': pair_sum, 'hull_length_m': length})
    for record in records:
        kind, identity = record.get('kind'), record.get('id')
        if kind == 'belt_main':
            declared_length = _number(record.get('length_m'))
            ratio = (declared_length / length / .65
                     if declared_length is not None and length is not None and length > 0 else None)
            ratio = _number(ratio)
            add('normal_length:' + identity, identity, 'normal_length', ratio is not None,
                values={'normal_length_ratio': ratio, 'declared_length_m': declared_length})
            known = declared_length is not None and minimum is not None
            add('minimum:' + identity, identity, 'main_coverage', known,
                warning=known and declared_length < minimum,
                values={'declared_length_m': declared_length, 'minimum_main_belt_length_m': minimum})
        if kind not in ('belt_main', 'belt_ends', 'belt_upper', 'bulge', 'bulkhead'):
            continue
        height, thickness = _number(record.get('height_m')), _number(record.get('thickness_mm'))
        limit = None
        inactive = kind in ('belt_main', 'belt_ends', 'belt_upper') and thickness == 0
        if kind == 'belt_upper':
            if free is not None and free >= 0:
                limit = free + .01 * .3048
        elif draft is not None and draft >= 0 and free is not None and free >= 0:
            if kind in ('bulge', 'bulkhead'):
                limit = draft + free
            elif angle is not None and -89 <= angle <= 89:
                limit = (draft + free) / math.cos(math.radians(abs(angle))) + .02 * .3048
        if limit is not None and not math.isfinite(limit):
            limit = None
        known = inactive or (height is not None and limit is not None and
                             (kind in ('bulge', 'bulkhead') or thickness is not None))
        add('height:' + identity, identity, 'height', known,
            warning=known and not inactive and height > limit,
            values={'maximum_height_m': limit, 'declared_height_m': height,
                    'inactive_zero_thickness': inactive})
    unavailable = [check for check in checks if check['status'] == 'unavailable']
    diagnostics = [dict(code='armour_review.dependency', severity='warning', blocking=False,
                        path=path + '.checks[' + check['id'] + ']',
                        message=check['message'] + ' Required facts are missing or ambiguous.')
                   for check in unavailable]
    return dict(method_version=METHOD_VERSION,
                status='partial' if unavailable else 'available',
                values={'minimum_main_belt_length_m': minimum}, checks=checks,
                diagnostics=diagnostics, provenance=dict(
                    source_location=SOURCE_LOCATION, source_sha256=source.SOURCE_SHA256,
                    method_version=METHOD_VERSION, declared_source=config.get('source'),
                    inputs=copy.deepcopy(facts), belt_inclination_deg=angle,
                    scope='Empirical dimensional review using declared/selected facts; '
                          'no protection rating, geometry reconstruction or mass adjustment.'))


MESSAGES = {
    'minimum_length': 'Minimum belt length uses the returned room ratio and composite strength >= 0.5.',
    'belt_pair': 'Exactly one main and one end belt must fit within the declared hull length.',
    'normal_length': 'Declared main belt length divided by 65 percent of hull length.',
    'main_coverage': 'Compare the declared main belt with the empirical machinery/magazine length.',
    'height': 'Compare declared height with the source rule for this region; inclination changes no mass.',
}
