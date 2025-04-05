from blockwork.workflows import Workflow

from ..config.run import Run


@Workflow("run").with_target(Run)
@staticmethod
def run(ctx, project, target):
    return target
