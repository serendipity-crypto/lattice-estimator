# -*- coding: utf-8 -*-
"""
High-level LWE interface
"""

from .lwe_primal import primal_usvp, primal_bdd, primal_hybrid
from .lwe_bkw import coded_bkw
from .lwe_guess import exhaustive_search, mitm, distinguish  # noqa
from .lwe_dual import dual, dual_hybrid
from .lwe_guess import guess_composition
from .gb import arora_gb  # noqa
from .lwe_parameters import LWEParameters as Parameters  # noqa


class Estimate:
    @classmethod
    def rough(cls, params, jobs=1):
        """
        This function makes the following somewhat routine assumptions:

        - The GSA holds.
        - The Core-SVP model holds.

        This function furthermore assumes the following heuristics:

        - The primal hybrid attack only applies to sparse secrets.
        - The dual hybrid MITM attack only applies to sparse secrets.
        - Arora-GB only applies to bounded noise with at least `n^2` samples.
        - BKW is not competitive.

        :param params: LWE parameters.
        :param jobs: Use multiple threads in parallel.

        EXAMPLE ::

            >>> from estimator import *
            >>> _ = lwe.estimate.rough(Kyber512)
            usvp                 :: rop: ≈2^118.6, red: ≈2^118.6, δ: 1.003941, β: 406, d: 998, tag: usvp
            dual_hybrid          :: rop: ≈2^121.9, mem: ≈2^116.8, m: 512, β: 417, d: 1013, ↻: 1, ζ: 11...


        """
        # NOTE: Don't import these at the top-level to avoid circular imports
        from functools import partial
        from .reduction import RC
        from .util import batch_estimate, f_name

        from sage.all import oo

        algorithms = {}

        algorithms["usvp"] = partial(primal_usvp, red_cost_model=RC.ADPS16, red_shape_model="gsa")

        if params.Xs.is_sparse:
            algorithms["hybrid"] = partial(
                primal_hybrid, red_cost_model=RC.ADPS16, red_shape_model="gsa"
            )

        if params.Xs.is_sparse:
            algorithms["dual_mitm_hybrid"] = partial(
                dual_hybrid, red_cost_model=RC.ADPS16, mitm_optimization=True
            )
        else:
            algorithms["dual_hybrid"] = partial(
                dual_hybrid, red_cost_model=RC.ADPS16, mitm_optimization=False
            )

        if params.m > params.n ** 2 and params.Xe.is_bounded:
            if params.Xs.is_sparse:
                algorithms["arora-gb"] = guess_composition(arora_gb.cost_bounded)
            else:
                algorithms["arora-gb"] = arora_gb.cost_bounded

        res_raw = batch_estimate(params, algorithms.values(), log_level=1, jobs=jobs)
        res_raw = res_raw[params]
        res = {}
        for algorithm in algorithms:
            for k, v in res_raw.items():
                if f_name(algorithms[algorithm]) == k:
                    res[algorithm] = v

        for algorithm in algorithms:
            for k, v in res.items():
                if algorithm == k:
                    if v["rop"] == oo:
                        continue
                    print(f"{algorithm:20s} :: {repr(v)}")
        return res

    def __call__(
        self,
        params,
        red_cost_model=None,
        red_shape_model=None,
        deny_list=tuple(),
        add_list=tuple(),
        jobs=1,
    ):
        """
        Run all estimates.

        :param params: LWE parameters.
        :param red_cost_model: How to cost lattice reduction.
        :param red_shape_model: How to model the shape of a reduced basis (applies to primal attacks)
        :param deny_list: skip these algorithms
        :param add_list: add these ``(name, function)`` pairs to the list of algorithms to estimate.a
        :param jobs: Use multiple threads in parallel.

        EXAMPLE ::

            >>> from estimator import *
            >>> _ = lwe.estimate(Kyber512)
            arora-gb             :: rop: ≈2^inf, dreg: 25, mem: ≈2^106.3, t: 3, m: ≈2^inf, tag: arora-gb, ↻: ≈2^inf, ζ: 480
            bkw                  :: rop: ≈2^178.8, m: ≈2^166.8, mem: ≈2^167.8, b: 14, t1: 0, t2: 16, ℓ: 13, #cod: 448, #top: 0, #test: 64, tag: coded-bkw
            usvp                 :: rop: ≈2^150.4, red: ≈2^150.4, δ: 1.003941, β: 406, d: 998, tag: usvp
            bdd                  :: rop: ≈2^146.9, red: ≈2^146.3, svp: ≈2^145.4, β: 391, η: 421, d: 1013, tag: bdd
            bdd_hybrid           :: rop: ≈2^146.9, red: ≈2^146.3, svp: ≈2^145.4, β: 391, η: 421, ζ: 0, |S|: 1, d: 1016, prob: 1, ↻: 1, tag: hybrid
            bdd_mitm_hybrid      :: rop: ≈2^297.5, red: ≈2^297.5, svp: ≈2^167.3, β: 405, η: 2, ζ: 0, |S|: 1, d: 1025, prob: ≈2^-145.1, ↻: ≈2^147.3, tag: hybrid
            dual                 :: rop: ≈2^157.4, mem: ≈2^81.0, m: 512, β: 431, d: 1024, ↻: 1, tag: dual
            dual_hybrid          :: rop: ≈2^151.7, mem: ≈2^147.5, m: 512, β: 410, d: 999, ↻: 1, ζ: 25, tag: dual_hybrid

        """
        from sage.all import oo
        from functools import partial
        from .conf import red_cost_model as red_cost_model_default
        from .conf import red_shape_model as red_shape_model_default
        from .util import batch_estimate, f_name

        if red_cost_model is None:
            red_cost_model = red_cost_model_default
        if red_shape_model is None:
            red_shape_model = red_shape_model_default

        algorithms = {}

        algorithms["arora-gb"] = guess_composition(arora_gb)
        algorithms["bkw"] = coded_bkw

        algorithms["usvp"] = partial(
            primal_usvp, red_cost_model=red_cost_model, red_shape_model=red_shape_model
        )
        algorithms["bdd"] = partial(
            primal_bdd, red_cost_model=red_cost_model, red_shape_model=red_shape_model
        )
        algorithms["bdd_hybrid"] = partial(
            primal_hybrid, mitm=False, babai=False, red_cost_model=red_cost_model,
            red_shape_model=red_shape_model
        )
        # we ignore the case of mitm=True babai=False for now, due to it being overly-optimistic
        algorithms["bdd_mitm_hybrid"] = partial(
            primal_hybrid, mitm=True, babai=True, red_cost_model=red_cost_model,
            red_shape_model=red_shape_model
        )
        algorithms["dual"] = partial(dual, red_cost_model=red_cost_model)
        algorithms["dual_hybrid"] = partial(
            dual_hybrid, red_cost_model=red_cost_model, mitm_optimization=False
        )
        algorithms["dual_mitm_hybrid"] = partial(
            dual_hybrid, red_cost_model=red_cost_model, mitm_optimization=True
        )

        for k in deny_list:
            del algorithms[k]
        for k, v in add_list:
            algorithms[k] = v

        res_raw = batch_estimate(params, algorithms.values(), log_level=1, jobs=jobs)
        res_raw = res_raw[params]
        res = {}
        for algorithm in algorithms:
            for k, v in res_raw.items():
                if f_name(algorithms[algorithm]) == k:
                    res[algorithm] = v

        for algorithm in algorithms:
            for k, v in res.items():
                if algorithm == k:
                    if v["rop"] == oo:
                        continue
                    if k == "hybrid" and res["bdd"]["rop"] < v["rop"]:
                        continue
                    if k == "dual_mitm_hybrid" and res["dual_hybrid"]["rop"] < v["rop"]:
                        continue
                    print(f"{algorithm:20s} :: {repr(v)}")
        return res


estimate = Estimate()
