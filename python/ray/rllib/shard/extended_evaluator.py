from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import ray
import numpy as np
from ray.rllib.optimizers import Evaluator
from ray.rllib.a3c.common import get_policy_cls
from ray.rllib.a3c.a3c_evaluator import A3CEvaluator
from ray.rllib.utils.filter import get_filter
from ray.rllib.utils.process_rollout import process_rollout


class ShardA3CEvaluator(A3CEvaluator):

    def __init__(self, registry, env_creator, config, logdir, pin_id=None, start_sampler=True):
        super(ShardA3CEvaluator, self).__init__(
            registry, env_creator, config, logdir, start_sampler)

        if pin_id:
            try:
                import psutil
                p = psutil.Process()
                p.cpu_affinity([pin_id])
                print("Setting CPU Affinity to: ", pin_id)
            except Exception as e:
                print(e)
                pass

    def compute_deltas(self, *shards): # NEED object IDs
        """
        Returns:
            delta_shards (list): list of shards
        """
        old_weights = reconstruct_weights(shards)
        self.set_flat(old_weights)
        grad = self.compute_gradients(self.sample())
        self.apply_gradients(grad)
        new_weights = self.get_flat()
        return shard(new_weights - old_weights, len(shards))

    def get_flat(self):
        return self.policy.variables.get_flat()

    def set_flat(self, weights):
        return self.policy.variables.set_flat(weights)


def setup_sharded(num_shards, force=False):
    ShardA3CEvaluator.compute_deltas = ray.method(
        num_return_vals=num_shards)(ShardA3CEvaluator.compute_deltas)
    if force:
        return ray.remote(num_gpus=1)(ShardA3CEvaluator)
    else:
        return ray.remote(ShardA3CEvaluator)

def shard(array, num):
    rets = np.array_split(array, num)
    return rets

def reconstruct_weights(shards):
    return np.concatenate(shards)

