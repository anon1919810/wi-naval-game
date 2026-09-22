# Resistance acceptance fixed before implementation

2026-09-22. Task 7 will implement explicitly versioned Holtrop–Mennen1982 full resistance. The1984 re-analysis is a different model, documented as such; no silent hybrid and no requirement to add a second version to complete the approved single Holtrop comparison method.

The source audit is at `.superpowers/sdd/2026-09-22-plimsoll-1.0/task-7-source-audit.md` during development and will be incorporated into tracked method documentation at integration. Formula authority: Holtrop and Mennen, *International Shipbuilding Progress*29(335),166–170,1982, [journal record](https://journals.sagepub.com/doi/10.3233/ISP-1982-2933501). Independent reproduction: E.Karageorgos2015 NTUA thesis, PDFpp85–86, [institutional copy](https://dspace.lib.ntua.gr/xmlui/bitstream/handle/123456789/42290/Karageorgos_Thesis.pdf?sequence=1). Do not redistribute paper scans.

## Fixed hypothetical benchmark

Use Lwl205 m, B32 m, fore/aft draft10 m, displacement volume37500 m3, Cm0.98, Cwp0.75, LCB=-0.75 percent of Lwl measured forward from its midpoint, bulb area20 m2, bulb centroid4 m above keel, immersed transom16 m2, appendage area50 m2 with equivalent factor1.50, stern factor input+10 and speed25 kn. Freeze rho1025 kg/m3, gravity9.81 m/s2, viscosity1.188e-6 m2/s and knot1852/3600 m/s. Let the source equation estimate wetted area, retaining that method label.

The independent thesis's1982 component values are RF869.47, RAPP8.83, RW556.63, RB0.049, RTR0 and RA220.53 kN; total1791.54 kN and effective power23039 kW. Compare all components, not just total. Predeclared tolerance is0.1% relative with absolute floor0.005 kN for values printed to0.01 kN; RB uses absolute0.0005 kN, and this benchmark's zero transom-coefficient branch should additionally be exactly zero. The0.1% allowance is derived from the primary/thesis component discrepancy (maximum0.0863% for RW after excluding the demonstrably inconsistent RA entry), before production implementation. Power tolerance0.1% with0.5 kW printed-resolution floor.

Check total aggregation and dimensional conversion at the global algebraic tolerance independently:

```
RT = RF*(1+k1) + RAPP + RW + RB + RTR + RA
PE_kW = RT_kN*V_mps
```

The1982 printed example has an internal inconsistency: CA0.000352/CF0.001390 differs from RA221.98/RF869.63. The identity RA/RF=CA/CF is independent of density, speed or area; its failure cannot be corrected by tuning those inputs. Therefore the paper's RA must not serve as the conformance target. Preserve the discrepant published values in documentation, with the unresolved cause explicitly stated. Its total1793.26 kN is only an informational comparison. The audit derives a2.23 kN discrepancy envelope from the invariant mismatch plus printed-digit rounding; this looser comparison cannot pass or replace the component tests.

This validates equation reproduction, not accuracy against a measured vessel. Do not imply a Queen Mary trial proves the coefficients or QPC. Keep unknown/estimated shape data, load condition and trial comparability visible.

## Numerical branches and limits

Test every piecewise boundary and define equality deterministically (use the middle branch at internal thresholds unless a source or continuity check requires otherwise). For zero bulb/transom area, short-circuit the dependent singular formulas. Missing area is unknown, not zero. An explicit empty appendage list represents the declared bare-hull scenario; absent appendage input is incomplete.

Reject invalid real-power bases, division singularities, nonfinite values and nonphysical coefficients. Reject unavailable total power rather than replacing missing components by zero. Return diagnostics for empirical-domain uncertainty independently of algebraic validity. The primary sources do not establish a universal CB>=0.55 cutoff; do not invent one.

For Schoenherr, preserve the legacy explicit approximation as a named compatibility method and provide the implicit original-line calculation for the new coordinator. Validate by choosing Cf first and constructing Re=10**(0.242/sqrt(Cf))/Cf; use the global exact-algebra tolerance for inverse consistency and residual. Include independent published table values after confirming their source precision. Do not label the existing power-law approximation an exact solution of the implicit equation.

Taylor normalization and table provenance must be resolved in Task7's source audit before marking the loading adapter verified. Normal/deep comparisons derive their own geometry and selected mass, not a reused design-waterline result. Roughness and QPC must be applied once, with method/source/estimate annotations.
