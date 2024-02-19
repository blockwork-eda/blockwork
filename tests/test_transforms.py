import pytest
from blockwork.build.transform import Transform
from blockwork.containers import ContainerError
from blockwork.config.api import ConfigApi

@pytest.mark.usefixtures('api')
class TestTransforms:

    def test_io_same_dir(self, api: ConfigApi):
        """
        Test that we get a bind error if a directory is used for both input and output.
        
        This may be something we want to (carefully) change later.
        """
        i = api.file_interface(api.ctx.host_scratch / '_/i')
        o = api.file_interface(api.ctx.host_scratch / '_/o')
        t = (Transform().bind_inputs(i=i)
                        .bind_outputs(o=o)
                        .bind_execute(lambda c, t, i: []))
        with pytest.raises(ContainerError):
            t.run(api.ctx)
