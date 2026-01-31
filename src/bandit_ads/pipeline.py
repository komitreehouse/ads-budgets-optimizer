"""
Pipeline orchestration for the data pipeline.

Manages workflows, job dependencies, monitoring, and health checks.
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import json

from src.bandit_ads.scheduler import get_scheduler, DataScheduler
from src.bandit_ads.data_collector import DataCollector, create_data_collector_from_config
from src.bandit_ads.etl import ETLPipeline
from src.bandit_ads.database import get_db_manager
from src.bandit_ads.db_helpers import get_api_error_rate
from src.bandit_ads.utils import get_logger, ConfigManager

logger = get_logger('pipeline')


class PipelineStatus(Enum):
    """Pipeline status enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class PipelineJob:
    """Represents a pipeline job."""
    
    def __init__(self, job_id: str, name: str, func: Callable, dependencies: List[str] = None):
        """
        Initialize pipeline job.
        
        Args:
            job_id: Unique job identifier
            name: Human-readable job name
            func: Function to execute
            dependencies: List of job IDs that must complete first
        """
        self.job_id = job_id
        self.name = name
        self.func = func
        self.dependencies = dependencies or []
        self.status = PipelineStatus.IDLE
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.error: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None


class PipelineManager:
    """Manages data pipeline workflows."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize pipeline manager.
        
        Args:
            config_manager: Optional configuration manager
        """
        self.config_manager = config_manager or ConfigManager()
        self.scheduler = get_scheduler()
        self.jobs: Dict[str, PipelineJob] = {}
        self.workflows: Dict[str, List[str]] = {}
        self.data_collector: Optional[DataCollector] = None
        self.etl_pipeline: Optional[ETLPipeline] = None
        
        # Initialize components
        self._initialize_components()
        
        logger.info("Pipeline manager initialized")
    
    def _initialize_components(self):
        """Initialize data collector and ETL pipeline."""
        try:
            config = self.config_manager.to_dict()
            self.data_collector = create_data_collector_from_config(config)
            self.etl_pipeline = ETLPipeline()
            logger.info("Pipeline components initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize some components: {str(e)}")
    
    def register_job(self, job: PipelineJob):
        """Register a pipeline job."""
        self.jobs[job.job_id] = job
        logger.info(f"Registered job: {job.name} ({job.job_id})")
    
    def define_workflow(self, workflow_id: str, job_ids: List[str]):
        """
        Define a workflow as a sequence of jobs.
        
        Args:
            workflow_id: Unique workflow identifier
            job_ids: Ordered list of job IDs
        """
        self.workflows[workflow_id] = job_ids
        logger.info(f"Defined workflow: {workflow_id} ({len(job_ids)} jobs)")
    
    def run_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Run a workflow.
        
        Args:
            workflow_id: Workflow identifier
        
        Returns:
            Dictionary with workflow results
        """
        if workflow_id not in self.workflows:
            return {'success': False, 'error': f'Workflow not found: {workflow_id}'}
        
        job_ids = self.workflows[workflow_id]
        results = {
            'workflow_id': workflow_id,
            'success': True,
            'jobs_completed': 0,
            'jobs_failed': 0,
            'start_time': datetime.utcnow(),
            'job_results': []
        }
        
        logger.info(f"Starting workflow: {workflow_id}")
        
        for job_id in job_ids:
            if job_id not in self.jobs:
                logger.error(f"Job not found: {job_id}")
                results['success'] = False
                results['jobs_failed'] += 1
                continue
            
            job = self.jobs[job_id]
            
            # Check dependencies
            for dep_id in job.dependencies:
                if dep_id not in self.jobs:
                    logger.error(f"Dependency not found: {dep_id}")
                    results['success'] = False
                    results['jobs_failed'] += 1
                    continue
                
                dep_job = self.jobs[dep_id]
                if dep_job.status != PipelineStatus.COMPLETED:
                    logger.error(f"Dependency not completed: {dep_id}")
                    results['success'] = False
                    results['jobs_failed'] += 1
                    break
            else:
                # All dependencies met, run job
                job_result = self._run_job(job)
                results['job_results'].append(job_result)
                
                if job_result['success']:
                    results['jobs_completed'] += 1
                else:
                    results['jobs_failed'] += 1
                    results['success'] = False
                    # Optionally stop workflow on failure
                    break
        
        results['end_time'] = datetime.utcnow()
        results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
        
        logger.info(f"Workflow {workflow_id} completed: {results['jobs_completed']} succeeded, {results['jobs_failed']} failed")
        return results
    
    def _run_job(self, job: PipelineJob) -> Dict[str, Any]:
        """Run a single job."""
        job.status = PipelineStatus.RUNNING
        job.start_time = datetime.utcnow()
        job.error = None
        job.result = None
        
        logger.info(f"Running job: {job.name} ({job.job_id})")
        
        try:
            result = job.func()
            job.result = result if isinstance(result, dict) else {'result': result}
            job.status = PipelineStatus.COMPLETED
            job.end_time = datetime.utcnow()
            
            success = result.get('success', True) if isinstance(result, dict) else True
            logger.info(f"Job {job.name} completed successfully")
            
            return {
                'job_id': job.job_id,
                'name': job.name,
                'success': success,
                'result': job.result,
                'duration': (job.end_time - job.start_time).total_seconds()
            }
            
        except Exception as e:
            job.status = PipelineStatus.FAILED
            job.error = str(e)
            job.end_time = datetime.utcnow()
            
            logger.error(f"Job {job.name} failed: {str(e)}")
            
            return {
                'job_id': job.job_id,
                'name': job.name,
                'success': False,
                'error': str(e),
                'duration': (job.end_time - job.start_time).total_seconds() if job.end_time else 0
            }
    
    def setup_default_workflows(self):
        """Setup default workflows."""
        if not self.data_collector or not self.etl_pipeline:
            logger.warning("Components not initialized, skipping default workflows")
            return
        
        # Hourly data collection job
        hourly_collection_job = PipelineJob(
            job_id='hourly_collection',
            name='Hourly Metrics Collection',
            func=self.data_collector.collect_all_active_campaigns
        )
        self.register_job(hourly_collection_job)
        
        # Daily aggregation and ETL job
        daily_etl_job = PipelineJob(
            job_id='daily_etl',
            name='Daily ETL Pipeline',
            func=self.etl_pipeline.run_etl_for_all_campaigns,
            dependencies=['hourly_collection']
        )
        self.register_job(daily_etl_job)
        
        # Define workflows
        self.define_workflow('hourly', ['hourly_collection'])
        self.define_workflow('daily', ['hourly_collection', 'daily_etl'])
        
        logger.info("Default workflows configured")
    
    def setup_scheduled_workflows(self):
        """Setup scheduled execution of workflows."""
        if not self.scheduler.running:
            self.scheduler.start()
        
        # Schedule hourly workflow
        self.scheduler.add_hourly_job(
            func=lambda: self.run_workflow('hourly'),
            job_id='scheduled_hourly_workflow',
            minute=0
        )
        
        # Schedule daily workflow
        self.scheduler.add_daily_job(
            func=lambda: self.run_workflow('daily'),
            job_id='scheduled_daily_workflow',
            hour=0,
            minute=0
        )
        
        logger.info("Scheduled workflows configured")
    
    def get_pipeline_health(self) -> Dict[str, Any]:
        """Get pipeline health status."""
        health = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {},
            'jobs': {},
            'api_health': {}
        }
        
        # Check database
        db_manager = get_db_manager()
        health['components']['database'] = db_manager.health_check()
        
        # Check scheduler
        if self.scheduler:
            try:
                health['components']['scheduler'] = self.scheduler.running
            except:
                health['components']['scheduler'] = False
        else:
            health['components']['scheduler'] = False
        
        # Check data collector
        health['components']['data_collector'] = self.data_collector is not None
        
        # Check ETL pipeline
        health['components']['etl_pipeline'] = self.etl_pipeline is not None
        
        # Check job statuses
        for job_id, job in self.jobs.items():
            health['jobs'][job_id] = {
                'status': job.status.value,
                'last_run': job.start_time.isoformat() if job.start_time else None,
                'error': job.error
            }
        
        # Check API health
        if self.data_collector:
            for platform in self.data_collector.api_connectors.keys():
                error_rate = get_api_error_rate(platform, hours=24)
                health['api_health'][platform] = {
                    'error_rate': error_rate,
                    'status': 'healthy' if error_rate < 0.1 else 'degraded' if error_rate < 0.3 else 'unhealthy'
                }
        
        # Overall status
        if not all(health['components'].values()):
            health['status'] = 'degraded'
        if any(rate > 0.3 for rate in [h.get('error_rate', 0) for h in health['api_health'].values()]):
            health['status'] = 'unhealthy'
        
        return health
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get pipeline performance metrics."""
        metrics = {
            'total_jobs': len(self.jobs),
            'completed_jobs': sum(1 for j in self.jobs.values() if j.status == PipelineStatus.COMPLETED),
            'failed_jobs': sum(1 for j in self.jobs.values() if j.status == PipelineStatus.FAILED),
            'running_jobs': sum(1 for j in self.jobs.values() if j.status == PipelineStatus.RUNNING),
            'workflows': len(self.workflows),
            'scheduled_jobs': len(self.scheduler.list_jobs()) if self.scheduler else 0
        }
        
        return metrics


def create_pipeline_manager(config_manager: Optional[ConfigManager] = None) -> PipelineManager:
    """
    Create and configure a pipeline manager.
    
    Args:
        config_manager: Optional configuration manager
    
    Returns:
        Configured PipelineManager instance
    """
    manager = PipelineManager(config_manager)
    manager.setup_default_workflows()
    manager.setup_scheduled_workflows()
    return manager
