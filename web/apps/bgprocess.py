import threading

class WorkerThread(threading.Thread):
    """A simple worker thread.

    Waits for tasks from the pool, performs them, and tells the pool about the
    result.

    """
    def __init__(self, pool):
        super(WorkerThread, self).__init__()
        self.pool = pool

    def run(self):
        """Run the worker thread.

        Exits when the pool returns no task.

        """
        try:
            while True:
                task_id, task = self.pool.wait_for_task()
                if task_id is None:
                    return
                progress = None
                try:
                    for progress in task.perform():
                        self.pool.set_progress(task_id, progress)
                        if progress.complete:
                            break
                except Exception, e:
                    import traceback
                    traceback.print_exc()
                    progress = TaskProgress("Task failed: %s" % e, failed=True)
                    self.pool.set_progress(task_id, progress)
                    continue

                if progress is None or not progress.complete:
                    progress = TaskProgress("Task complete", complete=True)
                    self.pool.set_progress(task_id, progress)
        finally:
            self.pool.worker_exited(self)


class TaskProgress(object):
    """A progress report from a task.

    """
    def __init__(self, msg, complete=False, failed=False):
        # Only one of complete and failed should be set.
        assert not (complete and failed)
        self.msg = msg
        self.complete = complete
        self.failed = failed

    def __str__(self):
        if self.complete:
            return "COMPLETE: %s" % self.msg
        if self.failed:
            return "FAILED: %s" % self.msg
        return str(self.msg)

class BackgroundPool(object):
    def __init__(self):
        self.cond = threading.Condition()
        self.workers = []
        self.dead_workers = [] # Workers which need to be waited on.
        self.waiting_workers = 0
        self.max_workers = 2
        self.task_queue = []
        self.next_id = 1
        self.progress = {} # Map from id to latest progress report

    def close(self):
        """Close the thread pool, and wait for the workers to finish.

        Called by main thread.
        
        """
        # print "Waiting for workers to finish"
        self.cond.acquire()
        try:
            self.max_workers = 0
            self.cond.notifyAll()

            while len(self.workers) > 0:
                self.cond.wait()
            for worker in self.dead_workers:
                worker.join()
            self.dead_workers = []
        finally:
            self.cond.release()
                
    def wait_for_task(self):
        """Called by worker to get another task.

        May block for a long time.  Returns None if the worker should exit.

        """
        self.cond.acquire()
        try:
            self.waiting_workers += 1
            while True:
                if self.max_workers == 0:
                    self.waiting_workers -= 1
                    return None, None
                if len(self.task_queue) > 0:
                    id, task = self.task_queue[0]
                    del self.task_queue[0]
                    self.waiting_workers -= 1
                    return id, task
                self.cond.wait()
        finally:
            self.cond.release()

    def worker_exited(self, worker):
        """Called by a worker when it exits."""
        self.cond.acquire()
        try:
            self.workers.remove(worker)
            self.dead_workers.append(worker)
            self.cond.notifyAll()
        finally:
            self.cond.release()

    def add_task(self, task):
        """Add a task to be performed.

        The task object must have a perform() method, which returns an iterator
        or is a generator, and yields a sequence of TaskProgress objects.  If
        an object with the "complete" flag is returned, the task will be
        considered complete, and iteration will be aborted.

        """
        self.cond.acquire()
        try:
            if self.max_workers == 0:
                raise ValueError("Starting background workers is forbidden - shutting down")

            id = self.next_id
            self.next_id += 1
            self.task_queue.append((id, task))
            self.progress[id] = TaskProgress("Queued")
            if (
                len(self.workers) < self.max_workers and
                self.waiting_workers == 0
            ):
                worker = WorkerThread(pool)
                self.workers.append(worker)
                worker.start()
            else:
                self.cond.notifyAll()
            return id
        finally:
            self.cond.release()

    def set_progress(self, id, status):
        """Set the progress report for a task.

        :param id: The ID of the task.
        :param status: The status of the task (a TaskStatus object).

        """
        self.cond.acquire()
        try:
            self.progress[id] = status
        finally:
            self.cond.release()
        #print id, status

    def get_progress(self, id):
        """Get the progress report for a task.

        """
        self.cond.acquire()
        try:
            try:
                return self.progress[id]
            except KeyError:
                return TaskProgress("Complete", complete=True)
        finally:
            self.cond.release()

pool = BackgroundPool()
