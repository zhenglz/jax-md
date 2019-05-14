# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for jax_md.space."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as onp

from absl.testing import absltest
from absl.testing import parameterized

from jax.config import config as jax_config
from jax import random
import jax.numpy as np

from jax.api import grad

from jax import test_util as jtu

from jax_md import space

jax_config.parse_flags_with_absl()
FLAGS = jax_config.FLAGS


PARTICLE_COUNT = 10
STOCHASTIC_SAMPLES = 10
SPATIAL_DIMENSION = [2, 3]


# pylint: disable=invalid-name
class SpaceTest(jtu.JaxTestCase):

  def test_small_inverse(self):
    key = random.PRNGKey(0)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split = random.split(key)
      mat = random.normal(split, (2, 2))

      inv_mat = space._small_inverse(mat)
      inv_mat_real_onp = onp.linalg.inv(mat)
      inv_mat_real_np = np.linalg.inv(mat)
      self.assertAllClose(inv_mat, inv_mat_real_onp, True)
      self.assertAllClose(inv_mat, inv_mat_real_np, True)

  # pylint: disable=g-complex-comprehension
  @parameterized.named_parameters(jtu.cases_from_list(
      {
          'testcase_name': '_dim={}'.format(dim),
          'spatial_dimension': dim
      } for dim in SPATIAL_DIMENSION))
  def test_transform(self, spatial_dimension):
    key = random.PRNGKey(0)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split1, split2 = random.split(key, 3)

      R = random.normal(split1, (PARTICLE_COUNT, spatial_dimension))
      T = random.normal(split2, (spatial_dimension, spatial_dimension))

      R_prime_exact = np.dot(R, T)
      R_prime = space.transform(T, R)

      self.assertAllClose(R_prime_exact, R_prime, True)

  # pylint: disable=g-complex-comprehension
  @parameterized.named_parameters(jtu.cases_from_list(
      {
          'testcase_name': '_dim={}'.format(dim),
          'spatial_dimension': dim
      } for dim in SPATIAL_DIMENSION))
  def test_transform_grad(self, spatial_dimension):
    key = random.PRNGKey(0)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split1, split2 = random.split(key, 3)

      R = random.normal(split1, (PARTICLE_COUNT, spatial_dimension))
      T = random.normal(split2, (spatial_dimension, spatial_dimension))

      R_prime = space.transform(T, R)

      energy_direct = lambda R: np.sum(R ** 2)
      energy_indirect = lambda T, R: np.sum(space.transform(T, R) ** 2)

      grad_direct = grad(energy_direct)(R_prime)
      grad_indirect = grad(energy_indirect, 1)(T, R)

      self.assertAllClose(grad_direct, grad_indirect, True)

  @parameterized.named_parameters(jtu.cases_from_list(
      {
          'testcase_name': '_dim={}'.format(dim),
          'spatial_dimension': dim
      } for dim in SPATIAL_DIMENSION))
  def test_transform_inverse(self, spatial_dimension):
    key = random.PRNGKey(0)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split1, split2 = random.split(key, 3)

      R = random.normal(split1, (PARTICLE_COUNT, spatial_dimension))

      T = random.normal(split2, (spatial_dimension, spatial_dimension))
      T_inv = space._small_inverse(T)

      R_test = space.transform(T_inv, space.transform(T, R))

      self.assertAllClose(R, R_test, True)

  @parameterized.named_parameters(jtu.cases_from_list(
      {
          'testcase_name': '_dim={}'.format(dim),
          'spatial_dimension': dim
      } for dim in SPATIAL_DIMENSION))
  def test_periodic_displacement(self, spatial_dimension):
    key = random.PRNGKey(0)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split = random.split(key)

      R = random.uniform(split, (PARTICLE_COUNT, spatial_dimension))
      dR = space.pairwise_displacement(R, R)

      dR_wrapped = space.periodic_displacement(1.0, dR)

      dR_direct = dR
      dr_direct = space.distance(dR)
      dr_direct = np.reshape(dr_direct, dr_direct.shape + (1,))

      if spatial_dimension == 2:
        for i in range(-1, 2):
          for j in range(-1, 2):
            dR_shifted = dR + np.array([i, j], dtype=np.float64)

            dr_shifted = space.distance(dR_shifted)
            dr_shifted = np.reshape(dr_shifted, dr_shifted.shape + (1,))

            dR_direct = np.where(dr_shifted < dr_direct, dR_shifted, dR_direct)
            dr_direct = np.where(dr_shifted < dr_direct, dr_shifted, dr_direct)
      elif spatial_dimension == 3:
        for i in range(-1, 2):
          for j in range(-1, 2):
            for k in range(-1, 2):
              dR_shifted = dR + np.array([i, j, k], dtype=np.float64)

              dr_shifted = space.distance(dR_shifted)
              dr_shifted = np.reshape(dr_shifted, dr_shifted.shape + (1,))

              dR_direct = np.where(
                  dr_shifted < dr_direct, dR_shifted, dR_direct)
              dr_direct = np.where(
                  dr_shifted < dr_direct, dr_shifted, dr_direct)

      dR_direct = np.array(dR_direct, dtype=dR.dtype)
      self.assertAllClose(dR_wrapped, dR_direct, True)

  @parameterized.named_parameters(jtu.cases_from_list(
      {
          'testcase_name': '_dim={}'.format(dim),
          'spatial_dimension': dim
      } for dim in SPATIAL_DIMENSION))
  def test_periodic_shift(self, spatial_dimension):
    key = random.PRNGKey(0)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split1, split2 = random.split(key, 3)

      R = random.uniform(split1, (PARTICLE_COUNT, spatial_dimension))
      dR = np.sqrt(0.1) * random.normal(
          split2, (PARTICLE_COUNT, spatial_dimension))

      dR = np.where(dR > 0.49, 0.49, dR)
      dR = np.where(dR < -0.49, -0.49, dR)

      R_shift = space.periodic_shift(1.0, R, dR)

      assert np.all(R_shift < 1.0)
      assert np.all(R_shift > 0.0)

      dR_after = space.periodic_displacement(1.0, R_shift - R)

      self.assertAllClose(dR_after, dR, True)

  @parameterized.named_parameters(jtu.cases_from_list(
      {
          'testcase_name': '_dim={}'.format(dim),
          'spatial_dimension': dim
      } for dim in SPATIAL_DIMENSION))
  def test_periodic_against_periodic_general(
      self, spatial_dimension):
    key = random.PRNGKey(0)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split1, split2, split3 = random.split(key, 4)

      max_box_size = 10.0
      box_size = max_box_size * random.uniform(split1, (spatial_dimension,))
      transform = np.diag(box_size)

      R = random.uniform(split2, (PARTICLE_COUNT, spatial_dimension))
      R_scaled = R * box_size

      dR = random.normal(split3, (PARTICLE_COUNT, spatial_dimension))

      disp_fn, shift_fn = space.periodic(box_size)
      general_disp_fn, general_shift_fn = space.periodic_general(transform)

      self.assertAllClose(
          disp_fn(R_scaled, R_scaled), general_disp_fn(R, R), True)
      self.assertAllClose(
          shift_fn(R_scaled, dR), general_shift_fn(R, dR) * box_size, True)

  @parameterized.named_parameters(jtu.cases_from_list(
      {
          'testcase_name': '_dim={}'.format(dim),
          'spatial_dimension': dim
      } for dim in SPATIAL_DIMENSION))
  def test_periodic_general_time_dependence(self, spatial_dimension):
    key = random.PRNGKey(0)

    eye = np.eye(spatial_dimension)

    for _ in range(STOCHASTIC_SAMPLES):
      key, split_T0_scale, split_T0_dT = random.split(key, 3)
      key, split_T1_scale, split_T1_dT = random.split(key, 3)
      key, split_t, split_R, split_dR = random.split(key, 4)

      size_0 = 10.0 * random.uniform(split_T0_scale, ())
      dtransform_0 = 0.5 * random.normal(
          split_T0_dT, (spatial_dimension, spatial_dimension))
      T_0 = size_0 * (eye + dtransform_0)

      size_1 = 10.0 * random.uniform(split_T1_scale, ())
      dtransform_1 = 0.5 * random.normal(
          split_T1_dT, (spatial_dimension, spatial_dimension))
      T_1 = size_1 * (eye + dtransform_1)

      T = lambda t: t * T_0 + (1.0 - t) * T_1

      t_g = random.uniform(split_t, ())

      disp_fn, shift_fn = space.periodic_general(T)
      true_disp_fn, true_shift_fn = space.periodic_general(T(t_g))

      R = random.uniform(split_R, (PARTICLE_COUNT, spatial_dimension))
      dR = random.normal(split_dR, (PARTICLE_COUNT, spatial_dimension))

      self.assertAllClose(disp_fn(R, R, t_g), true_disp_fn(R, R), True)
      self.assertAllClose(shift_fn(R, dR, t_g), true_shift_fn(R, dR), True)


if __name__ == '__main__':
  absltest.main()