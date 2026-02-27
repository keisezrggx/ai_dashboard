import os
import time
import random
import glob
import nbformat

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from nbconvert.preprocessors import ExecutePreprocessor, CellExecutionError

# Config / Data Structures

@dataclass
class NotebookJob:
    notebook_path: str
    required_csv: List[str]

@dataclass
class JobResult:
    notebook_path: str
    success: bool
    attempts: int
    error: Optional[str]
    missing_csv: List[str]

# Exponential Backoff

def exponential_backoff_sleep(
        attempt: int,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        jitter: float = 0.25
) -> None:
    """
    attempt: 1,2,3,...
    delay = min(max_delay, base_delay * 2^(attempt-1)) * random_jitter
    """
    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    # jitter factor around 1.0(e.g. 0.75 to 1.25 if jitter=0.25)
    jitter_factor = 1.0 + random.uniform(-jitter, jitter)
    time.sleep(max(0.0, delay * jitter_factor))

# Checks

def file_exists(path: str) -> bool:
    return os.path.isfile(path)

def missing_files(paths: List[str]) -> List[str]:
    return [p for p in paths if not file_exists(p)]

# Notebook Execution

def execute_notebook(
        notebook_path: str,
        timeout: int = 1800,
        kernel_name: str = 'python3'
) -> None:
    """
    Execute notebook in-place.
    Raises CellExecutionError on failure.
    """
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)

    ep = ExecutePreprocessor(timeout=timeout, kernel_name=kernel_name)

    # Set working directory to notebook's folder
    nb_dir = os.path.dirname(notebook_path)

    ep.preprocess(nb, {'metadata': {'path': nb_dir}})

# Runner

def run_job_with_retries(
        job: NotebookJob,
        max_retries: int = 3,
        timeout: int = 1800,
) -> JobResult:
    """
    1. Check notebook file exists
    2. Execute notebook
    3. Ceheck for required CSV files
    Retry with exponential backoff if execution fails or CSVs are missing.
    """

    nb_path = job.notebook_path
    req_csv = job.required_csv

    if not file_exists(nb_path):
        return JobResult(
            notebook_path=nb_path,
            success=False,
            attempts=0,
            error=f'Notebook tidak ditemukan: {nb_path}',
            missing_csv=req_csv[:]
        )
    
    last_err = None
    last_missing = []

    for attempt in range(1, max_retries + 1):
        try:
            execute_notebook(nb_path, timeout=timeout)

            last_missing = missing_files(req_csv)
            if last_missing:
                raise FileNotFoundError(
                    f'CSV belum lengkap setelah eksekusi: {last_missing}'
                )
            
            return JobResult(
                notebook_path=nb_path,
                success=True,
                attempts=attempt,
                error=None,
                missing_csv=[]
            )

        except (CellExecutionError, TimeoutError, FileNotFoundError, Exception) as e:
            last_err = str(e)

            if attempt < max_retries:
                exponential_backoff_sleep(attempt)
            else:
                break
    
    return JobResult(
        notebook_path=nb_path,
        success=False,
        attempts=max_retries,
        error=last_err,
        missing_csv=last_missing
    )

def discover_notebooks(notebook_dir: str, pattern: str = '*.ipynb') -> List[str]:
    return sorted(glob.glob(os.path.join(notebook_dir, pattern)))

def run_all_jobs(
        jobs: List[NotebookJob],
        max_retries: int = 3,
        timeout: int = 1800,
) -> List[JobResult]:
    result = []
    for job in jobs:
        res = run_job_with_retries(job, max_retries=max_retries, timeout=timeout)
        result.append(res)
    return result

def print_summary(results: List[JobResult]) -> None:
    ok = [r for r in results if r.success]
    bad = [r for r in results if not r.success]

    print('=' * 60)
    print(f'Total: {len(results)} | Success: {len(ok)} | Failed: {len(bad)}')
    print('=' * 60)

    if ok:
        print('\n Success.')
        for r in ok:
            print(f'- {r.notebook_path} (attempts: {r.attempts})')
        
    if bad:
        print('\n Failed.')
        for r in bad:
            print(f'- {r.notebook_path} (attempts={r.attempts})')
            if r.error:
                print(f'  Error: {r.error}')
            if r.missing_csv:
                print(f'  Missing CSV: {r.missing_csv}')

# Example Usage

if __name__ == '__main__':
    # Contoh: definisikan mapping notebook -> CSV yang wajib ada
    jobs = [
        
    ]

    result = run_all_jobs(jobs, max_retries=3, timeout=1800)
    print_summary(result)

    if any(not r.success for r in result):
        raise SystemExit(1)