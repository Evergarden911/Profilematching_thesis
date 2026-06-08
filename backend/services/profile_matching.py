"""
Profile Matching Service
========================
Mengimplementasikan algoritma Profile Matching standar dengan dukungan
interpolasi linier berkesinambungan untuk menjaga presisi desimal,
serta pengamanan terhadap kegagalan pembagian matematis.

Gap = Skor Karyawan - Nilai Target
"""

from dataclasses import dataclass

CF_WEIGHT: float = 0.6
SF_WEIGHT: float = 0.4

# Tabel standar konversi selisih (Gap)
GAP_TABLE: dict[int, float] = {
    0: 5.0,
    1: 4.5,
    -1: 4.0,
    2: 3.5,
    -2: 3.0,
    3: 2.5,
    -3: 2.0,
    4: 1.5,
    -4: 1.0,
}

@dataclass
class CriteriaInput:
    criteria_id: int
    employee_score: float
    target_value: float
    weight: float
    factor_type: str


@dataclass
class EmployeeMatchResult:
    employee_id: int
    ncf_score: float
    nsf_score: float
    final_score: float
    gap_detail: dict[int, float]


def _compute_gap_weight(employee_score: float, target_value: float) -> float:
    gap = employee_score - target_value
    
    # Optimasi untuk nilai bulat mutlak
    if gap.is_integer() and int(gap) in GAP_TABLE:
        return GAP_TABLE[int(gap)]
        
    # Interpolasi Linier untuk kesenjangan angka desimal
    lower_bound = int(gap // 1)
    upper_bound = lower_bound + 1
    
    # Pembatasan nilai ekstrem di luar jangkauan tabel
    if lower_bound < -4: return 1.0
    if upper_bound > 4: return 1.5
    
    lower_val = GAP_TABLE.get(lower_bound, 1.0)
    upper_val = GAP_TABLE.get(upper_bound, 1.5)
    
    fraction = gap - lower_bound
    return lower_val + (upper_val - lower_val) * fraction


def _weighted_average(pairs: list[tuple[float, float]]) -> float:
    total_weight = sum(w for _, w in pairs)
    if total_weight == 0.0:
        return 0.0
    return sum(score * w for score, w in pairs) / total_weight


def compute_match(employee_id: int, criteria_inputs: list[CriteriaInput]) -> EmployeeMatchResult:
    core_pairs: list[tuple[float, float]] = []
    secondary_pairs: list[tuple[float, float]] = []
    gap_detail: dict[int, float] = {}

    for ci in criteria_inputs:
        gw = _compute_gap_weight(ci.employee_score, ci.target_value)
        gap_detail[ci.criteria_id] = round(gw, 4)

        if ci.factor_type == "core":
            core_pairs.append((gw, ci.weight))
        else:
            secondary_pairs.append((gw, ci.weight))

    ncf = _weighted_average(core_pairs)
    nsf = _weighted_average(secondary_pairs)
    
    # Penyesuaian dinamis jika divisi memiliki struktur kriteria asimetris
    if core_pairs and not secondary_pairs:
        final = ncf
    elif secondary_pairs and not core_pairs:
        final = nsf
    else:
        final = CF_WEIGHT * ncf + SF_WEIGHT * nsf

    return EmployeeMatchResult(
        employee_id=employee_id,
        ncf_score=round(ncf, 4),
        nsf_score=round(nsf, 4),
        final_score=round(final, 4),
        gap_detail=gap_detail,
    )


def rank_employees(results: list[EmployeeMatchResult]) -> list[tuple[int, EmployeeMatchResult]]:
    sorted_results = sorted(results, key=lambda r: r.final_score, reverse=True)

    ranked: list[tuple[int, EmployeeMatchResult]] = []
    current_rank = 1
    for i, r in enumerate(sorted_results):
        if i > 0 and r.final_score < sorted_results[i - 1].final_score:
            current_rank = i + 1
        ranked.append((current_rank, r))
    return ranked