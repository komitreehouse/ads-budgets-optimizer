"""
Meridian Model Training Pipeline

Handles offline Meridian model fitting, posterior serialization, convergence
diagnostics, and model lifecycle management.  Trained models are persisted to
disk so the online inference service can load them without re-running MCMC.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from src.bandit_ads.utils import get_logger, ConfigManager

logger = get_logger("meridian_trainer")

DEFAULT_MODEL_DIR = "data/meridian_model"
DEFAULT_MCMC_SAMPLES = 2000
DEFAULT_MCMC_WARMUP = 1000
DEFAULT_MCMC_CHAINS = 4
DEFAULT_CONVERGENCE_THRESHOLD = 1.05


class TrainingResult:
    """Container for training outcomes."""

    def __init__(
        self,
        success: bool,
        campaign_id: Optional[int],
        model_path: Optional[str] = None,
        diagnostics: Optional[Dict] = None,
        error: Optional[str] = None,
        trained_at: Optional[str] = None,
    ):
        self.success = success
        self.campaign_id = campaign_id
        self.model_path = model_path
        self.diagnostics = diagnostics or {}
        self.error = error
        self.trained_at = trained_at or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "campaign_id": self.campaign_id,
            "model_path": self.model_path,
            "diagnostics": self.diagnostics,
            "error": self.error,
            "trained_at": self.trained_at,
        }


class MeridianTrainer:
    """Offline Meridian model training and persistence."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or self._load_config()
        self.model_dir = cfg.get("model_path", DEFAULT_MODEL_DIR)
        self.mcmc_samples = cfg.get("mcmc_samples", DEFAULT_MCMC_SAMPLES)
        self.mcmc_warmup = cfg.get("mcmc_warmup", DEFAULT_MCMC_WARMUP)
        self.mcmc_chains = cfg.get("mcmc_chains", DEFAULT_MCMC_CHAINS)
        self.convergence_threshold = cfg.get(
            "convergence_threshold", DEFAULT_CONVERGENCE_THRESHOLD
        )
        self.min_training_weeks = cfg.get("min_training_weeks", 12)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(
        self,
        campaign_id: Optional[int] = None,
        prior_config: Optional[Dict] = None,
    ) -> TrainingResult:
        """
        Train a Meridian model for a campaign (or cross-campaign if None).

        Steps:
        1. Extract & validate data via meridian_data
        2. Build Meridian InputData
        3. Configure ModelSpec (with optional informative priors)
        4. Run MCMC
        5. Validate convergence
        6. Persist posterior samples

        Returns a TrainingResult.
        """
        from src.bandit_ads.meridian_data import (
            extract_meridian_dataset,
            build_meridian_input_data,
            get_channel_names,
        )

        label = f"campaign {campaign_id}" if campaign_id else "cross-campaign"
        logger.info(f"Starting Meridian training for {label}")

        # Step 1: data extraction
        df = extract_meridian_dataset(
            campaign_id=campaign_id,
            min_weeks=self.min_training_weeks,
        )
        if df is None:
            return TrainingResult(
                success=False,
                campaign_id=campaign_id,
                error="Insufficient data for training",
            )

        # Step 2: build Meridian InputData
        try:
            input_data = build_meridian_input_data(df)
        except ImportError:
            return TrainingResult(
                success=False,
                campaign_id=campaign_id,
                error="google-meridian not installed",
            )
        except Exception as exc:
            return TrainingResult(
                success=False,
                campaign_id=campaign_id,
                error=f"Failed to build InputData: {exc}",
            )

        # Step 3: configure model spec
        try:
            from meridian.model import model_spec as ms
            from meridian.model import meridian_model

            spec = self._build_model_spec(
                channel_names=get_channel_names(df),
                prior_config=prior_config,
            )
        except ImportError:
            return TrainingResult(
                success=False,
                campaign_id=campaign_id,
                error="google-meridian not installed",
            )
        except Exception as exc:
            return TrainingResult(
                success=False,
                campaign_id=campaign_id,
                error=f"Failed to build ModelSpec: {exc}",
            )

        # Step 4: fit model
        try:
            model = meridian_model.MeridianModel(
                input_data=input_data,
                model_spec=spec,
            )
            model.fit(
                num_samples=self.mcmc_samples,
                num_warmup=self.mcmc_warmup,
                num_chains=self.mcmc_chains,
            )
        except Exception as exc:
            return TrainingResult(
                success=False,
                campaign_id=campaign_id,
                error=f"MCMC fitting failed: {exc}",
            )

        # Step 5: convergence diagnostics
        diagnostics = self._check_convergence(model)
        if not diagnostics.get("passed"):
            logger.warning(
                f"Convergence check failed for {label}: {diagnostics}"
            )
            return TrainingResult(
                success=False,
                campaign_id=campaign_id,
                diagnostics=diagnostics,
                error="Model did not converge — not publishing",
            )

        # Step 6: persist
        model_path = self._persist_model(model, campaign_id, df, diagnostics)

        logger.info(f"Meridian training completed for {label} → {model_path}")
        return TrainingResult(
            success=True,
            campaign_id=campaign_id,
            model_path=model_path,
            diagnostics=diagnostics,
        )

    def load_model(self, campaign_id: Optional[int] = None) -> Optional[Any]:
        """
        Load a previously trained Meridian model from disk.

        Returns the MeridianModel object or None if not found.
        """
        model_path = self._campaign_model_path(campaign_id)
        if not os.path.exists(model_path):
            return None

        meta_path = os.path.join(model_path, "meta.json")
        if not os.path.exists(meta_path):
            return None

        try:
            from meridian.model import meridian_model

            model = meridian_model.MeridianModel.load(model_path)
            logger.info(f"Loaded Meridian model from {model_path}")
            return model
        except Exception as exc:
            logger.warning(f"Failed to load Meridian model: {exc}")
            return None

    def has_trained_model(self, campaign_id: Optional[int] = None) -> bool:
        """Check whether a valid trained model exists."""
        model_path = self._campaign_model_path(campaign_id)
        meta_path = os.path.join(model_path, "meta.json")
        return os.path.exists(meta_path)

    def get_training_status(
        self, campaign_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get metadata about the latest trained model."""
        model_path = self._campaign_model_path(campaign_id)
        meta_path = os.path.join(model_path, "meta.json")
        if not os.path.exists(meta_path):
            return {"trained": False}

        with open(meta_path) as f:
            meta = json.load(f)
        meta["trained"] = True
        return meta

    def get_convergence_diagnostics(
        self, campaign_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Return convergence diagnostics for the latest model."""
        status = self.get_training_status(campaign_id)
        return status.get("diagnostics", {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_model_spec(
        self,
        channel_names: list,
        prior_config: Optional[Dict] = None,
    ) -> Any:
        """Build a Meridian ModelSpec with optional informative priors."""
        from meridian.model import model_spec as ms

        # Start with default spec — Meridian uses Hill-Adstock by default
        spec_kwargs: Dict[str, Any] = {}

        # Apply informative priors from incrementality experiments
        if prior_config:
            for ch_safe, prior in prior_config.items():
                if ch_safe in channel_names:
                    logger.info(
                        f"Applying informative prior for {ch_safe}: "
                        f"mean={prior['mean']:.3f}, std={prior['std']:.3f}"
                    )
            # Meridian's ModelSpec accepts prior overrides via its constructor.
            # The exact API depends on the Meridian version; we pass them
            # through so the caller can extend as Meridian evolves.
            spec_kwargs["prior_config"] = prior_config

        spec = ms.ModelSpec(**spec_kwargs)
        return spec

    def _check_convergence(self, model: Any) -> Dict[str, Any]:
        """
        Validate MCMC convergence using R-hat and divergence counts.

        Returns a diagnostics dict with a 'passed' boolean.
        """
        try:
            import arviz as az

            inference_data = model.get_inference_data()
            summary = az.summary(inference_data)

            max_rhat = float(summary["r_hat"].max())
            min_ess = float(summary["ess_bulk"].min())
            n_divergences = int(
                inference_data.sample_stats["diverging"].sum()
                if "diverging" in inference_data.sample_stats
                else 0
            )

            passed = (
                max_rhat <= self.convergence_threshold
                and n_divergences == 0
                and min_ess >= 400
            )

            return {
                "passed": passed,
                "max_rhat": round(max_rhat, 4),
                "min_ess_bulk": round(min_ess, 1),
                "n_divergences": n_divergences,
                "convergence_threshold": self.convergence_threshold,
            }
        except Exception as exc:
            logger.warning(f"Could not compute convergence diagnostics: {exc}")
            return {"passed": False, "error": str(exc)}

    def _persist_model(
        self,
        model: Any,
        campaign_id: Optional[int],
        df: Any,
        diagnostics: Dict,
    ) -> str:
        """Save model and metadata to disk."""
        model_path = self._campaign_model_path(campaign_id)

        # Clean previous model
        if os.path.exists(model_path):
            shutil.rmtree(model_path)
        os.makedirs(model_path, exist_ok=True)

        # Save the Meridian model
        try:
            model.save(model_path)
        except Exception as exc:
            logger.warning(
                f"model.save() failed ({exc}); saving posterior samples instead"
            )
            # Fallback: save posterior samples as numpy arrays
            self._save_posteriors_numpy(model, model_path)

        # Save metadata
        meta = {
            "campaign_id": campaign_id,
            "trained_at": datetime.utcnow().isoformat(),
            "n_weeks": int(len(df)),
            "date_range": {
                "start": str(df["date"].min()),
                "end": str(df["date"].max()),
            },
            "diagnostics": diagnostics,
            "mcmc_config": {
                "samples": self.mcmc_samples,
                "warmup": self.mcmc_warmup,
                "chains": self.mcmc_chains,
            },
        }
        with open(os.path.join(model_path, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2, default=str)

        return model_path

    def _save_posteriors_numpy(self, model: Any, path: str) -> None:
        """Fallback: extract and save posterior samples as .npz."""
        try:
            inference_data = model.get_inference_data()
            posterior = inference_data.posterior
            arrays = {}
            for var in posterior.data_vars:
                arrays[var] = posterior[var].values
            np.savez(os.path.join(path, "posteriors.npz"), **arrays)
        except Exception as exc:
            logger.error(f"Failed to save posteriors: {exc}")

    def _campaign_model_path(self, campaign_id: Optional[int]) -> str:
        """Get the directory for a campaign's model."""
        if campaign_id is None:
            return os.path.join(self.model_dir, "cross_campaign")
        return os.path.join(self.model_dir, str(campaign_id))

    @staticmethod
    def _load_config() -> Dict:
        """Load Meridian config from the project config file."""
        try:
            cm = ConfigManager()
            return cm.get("mmm.meridian", {})
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# Convenience function for scheduler integration
# ---------------------------------------------------------------------------


def train_all_campaigns() -> Dict[str, Any]:
    """
    Train Meridian models for all active campaigns with sufficient data.

    Intended to be called by DataScheduler as a daily job.
    """
    from src.bandit_ads.database import Campaign, get_db_manager

    trainer = MeridianTrainer()
    db_manager = get_db_manager()
    results = {"trained": [], "skipped": [], "failed": []}

    with db_manager.get_session() as session:
        campaigns = (
            session.query(Campaign).filter(Campaign.status == "active").all()
        )
        campaign_ids = [c.id for c in campaigns]

    # Train per-campaign models
    for cid in campaign_ids:
        result = trainer.train(campaign_id=cid)
        if result.success:
            results["trained"].append(cid)
        elif "Insufficient data" in (result.error or ""):
            results["skipped"].append(cid)
        else:
            results["failed"].append({"campaign_id": cid, "error": result.error})

    # Also train cross-campaign model
    cross = trainer.train(campaign_id=None)
    if cross.success:
        results["trained"].append("cross_campaign")

    logger.info(
        f"Meridian batch training: {len(results['trained'])} trained, "
        f"{len(results['skipped'])} skipped, {len(results['failed'])} failed"
    )
    return results
