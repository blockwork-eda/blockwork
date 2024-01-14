# Copyright 2023, Blockwork, github.com/intuity/blockwork
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from blockwork.common.scopedapi import ScopedApi, ApiAccessError

class TestSubApi:
    def __init__(self, api, subk: int):
        self.api = api.fork(sub=self)
        self.subk = subk

class TestApi:

    def test_api(self):
        k0 = 'a'
        k0_api = ScopedApi(k0=k0)
        assert k0_api.k0 == k0

        with pytest.raises(ApiAccessError):
            assert k0_api.k1 == k1

        k1 = 'b'
        k0_k1_api = k0_api.fork(k1=k1)
        assert k0_k1_api.k0 == k0
        assert k0_k1_api.k1 == k1

        # Check that fork doesn't impact original
        with pytest.raises(ApiAccessError):
            assert k0_api.k1 == k1

    def test_subapi(self):
        k0 = 'a'
        api = ScopedApi(k0=k0)
        k1 = 'b'
        subapi = TestSubApi(api, subk=k1).api
        
        assert subapi.k0 == k0
        assert subapi.sub.subk == k1

    def test_scoping(self):
        k0 = 'a'

        def pretend_external_call(callback):
            callback()

        def pretend_callback():
            api = ScopedApi.current
            assert api.k0 == k0
        
        with ScopedApi(k0=k0):
            pretend_external_call(pretend_callback)

