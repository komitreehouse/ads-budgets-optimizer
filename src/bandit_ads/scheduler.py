"""
Scheduled data collection using APScheduler.

Handles scheduled jobs for pulling data from APIs, aggregating metrics,
and updating MMM coefficients.
"""

from typing import Callable, Optional, Dict, Any, List
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import pytz

from src.bandit_ads.utils import get_logger

logger = get_logger('scheduler')


class DataScheduler:
    """Manages scheduled jobs for data collection."""
    
    def __init__(self, timezone: str = 'UTC'):
        """
        Initialize the scheduler.
        
        Args:
            timezone: Timezone for scheduling (default: UTC)
        """
        self.timezone = pytz.timezone(timezone)
        self.scheduler = BackgroundScheduler(
            jobstores={'default': MemoryJobStore()},
            executors={'default': ThreadPoolExecutor(10)},
            job_defaults={
                'coalesce': True,  # Combine multiple pending executions
                'max_instances': 1,  # Only one instance of each job at a time
                'misfire_grace_time': 300  # 5 minutes grace period
            },
            timezone=self.timezone
        )
        self.jobs: Dict[str, Any] = {}  # Track job metadata
        self._is_running = False
        logger.info(f"Scheduler initialized with timezone: {timezone}")
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            self._is_running = True
            logger.info("Scheduler started")
        else:
            logger.warning("Scheduler is already running")
            self._is_running = True
    
    def stop(self, wait: bool = True):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            self._is_running = False
            logger.info("Scheduler stopped")
        else:
            logger.warning("Scheduler is not running")
            self._is_running = False
    
    @property
    def running(self) -> bool:
        """Check if scheduler is running."""
        try:
            return self.scheduler.running
        except:
            return getattr(self, '_is_running', False)
    
    def add_hourly_job(self, func: Callable, job_id: str, 
                       minute: int = 0, **kwargs) -> str:
        """
        Add a job that runs every hour.
        
        Args:
            func: Function to execute
            job_id: Unique identifier for the job
            minute: Minute of the hour to run (0-59)
            **kwargs: Additional arguments to pass to the function
        
        Returns:
            Job ID
        """
        trigger = CronTrigger(minute=minute)
        job = self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs,
            replace_existing=True
        )
        self.jobs[job_id] = job
        logger.info(f"Added hourly job: {job_id} (runs at :{minute:02d} past each hour)")
        return job_id
    
    def add_daily_job(self, func: Callable, job_id: str,
                     hour: int = 0, minute: int = 0, **kwargs) -> str:
        """
        Add a job that runs daily.
        
        Args:
            func: Function to execute
            job_id: Unique identifier for the job
            hour: Hour of day to run (0-23)
            minute: Minute of hour to run (0-59)
            **kwargs: Additional arguments to pass to the function
        
        Returns:
            Job ID
        """
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs,
            replace_existing=True
        )
        self.jobs[job_id] = job
        logger.info(f"Added daily job: {job_id} (runs at {hour:02d}:{minute:02d})")
        return job_id
    
    def add_interval_job(self, func: Callable, job_id: str,
                        hours: Optional[int] = None,
                        minutes: Optional[int] = None,
                        seconds: Optional[int] = None,
                        **kwargs) -> str:
        """
        Add a job that runs at regular intervals.
        
        Args:
            func: Function to execute
            job_id: Unique identifier for the job
            hours: Interval in hours
            minutes: Interval in minutes
            seconds: Interval in seconds
            **kwargs: Additional arguments to pass to the function
        
        Returns:
            Job ID
        """
        if hours:
            trigger = IntervalTrigger(hours=hours)
        elif minutes:
            trigger = IntervalTrigger(minutes=minutes)
        elif seconds:
            trigger = IntervalTrigger(seconds=seconds)
        else:
            raise ValueError("Must specify hours, minutes, or seconds")
        
        job = self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs,
            replace_existing=True
        )
        self.jobs[job_id] = job
        interval_str = f"{hours}h" if hours else f"{minutes}m" if minutes else f"{seconds}s"
        logger.info(f"Added interval job: {job_id} (runs every {interval_str})")
        return job_id
    
    def remove_job(self, job_id: str):
        """Remove a scheduled job."""
        try:
            # Try to remove from scheduler (may not exist if scheduler not started)
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass  # Job may not exist in scheduler yet
            
            # Remove from our tracking
            if job_id in self.jobs:
                del self.jobs[job_id]
            
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            logger.warning(f"Error removing job {job_id}: {str(e)}")
    
    def get_job(self, job_id: str):
        """Get a job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all scheduled jobs."""
        jobs = []
        # Get all jobs from the scheduler
        scheduler_jobs = self.scheduler.get_jobs()
        for scheduler_job in scheduler_jobs:
            jobs.append({
                'id': scheduler_job.id,
                'name': scheduler_job.name or scheduler_job.id,
                'next_run_time': scheduler_job.next_run_time.isoformat() if scheduler_job.next_run_time else None,
                'trigger': str(scheduler_job.trigger)
            })
        return jobs
    
    def pause_job(self, job_id: str):
        """Pause a job."""
        if job_id in self.jobs:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")
        else:
            logger.warning(f"Job not found: {job_id}")
    
    def resume_job(self, job_id: str):
        """Resume a paused job."""
        if job_id in self.jobs:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")
        else:
            logger.warning(f"Job not found: {job_id}")


# Global scheduler instance
_scheduler: Optional[DataScheduler] = None


def get_scheduler(timezone: str = 'UTC') -> DataScheduler:
    """
    Get or create the global scheduler instance.
    
    Args:
        timezone: Timezone for scheduling (only used on first call)
    
    Returns:
        DataScheduler instance
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = DataScheduler(timezone)
    return _scheduler
