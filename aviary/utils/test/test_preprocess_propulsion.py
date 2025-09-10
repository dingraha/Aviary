import unittest

import numpy as np

# from openmdao.utils.assert_utils import assert_near_equal

import aviary.api as av

# from aviary.models.aircraft.multi_engine_single_aisle.multi_engine_single_aisle_data import (
#     engine_1_inputs,
#     engine_2_inputs,
#     # inputs,
# )
# from aviary.subsystems.propulsion.utils import build_engine_deck
from aviary.utils.aviary_values import AviaryValues
# from aviary.variable_info.enums import LegacyCode
# from aviary.subsystems.aerodynamics.aerodynamics_builder import CoreAerodynamicsBuilder
from aviary.subsystems.aerodynamics.aerodynamics_builder import AerodynamicsBuilderBase
from aviary.subsystems.propulsion.engine_model import EngineModel
# from aviary.subsystems.geometry.geometry_builder import CoreGeometryBuilder
# from aviary.subsystems.mass.mass_builder import CoreMassBuilder
# from aviary.subsystems.propulsion.propulsion_builder import CorePropulsionBuilder
from aviary.variable_info.variable_meta_data import _MetaData

from aviary.utils.preprocessors import preprocess_propulsion

# GASP = LegacyCode.GASP
# FLOPS = LegacyCode.FLOPS

from aviary.variable_info.variables import Aircraft as AviaryAircraft

class Aircraft(AviaryAircraft):
    class Engine(AviaryAircraft.Engine):
        DO_FOO = "aircraft:engine:do_foo"
        FOO_INPUT_SCALAR0 = "aircraft:engine:foo_input_scalar0"
        FOO_INPUT_VECTOR0 = "aircraft:engine:foo_input_vector0"


ExtendedMetaData = av.CoreMetaData

av.add_meta_data(
    Aircraft.Engine.DO_FOO,
    desc="do foo",
    default_value=True,
    types=bool,
    multivalue=True,
    option=True,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Engine.FOO_INPUT_SCALAR0,
    units="lbf",
    desc="foo engine scalar0",
    default_value=0.123,
    types=float,
    multivalue=True,
    option=False,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Engine.FOO_INPUT_VECTOR0,
    units="m",
    desc="foo engine vector0",
    default_value=0.234,
    types=(float, np.ndarray),
    multivalue=True,
    option=False,
    meta_data=ExtendedMetaData
)

class FakeAerodynamicsBuilder(AerodynamicsBuilderBase):
    def __init__(self, name=None, meta_data=None):
        if name is None:
            name = 'fake_aerodynamics'

        super().__init__(name=name, meta_data=meta_data)

    def get_engine_options(self, aviary_inputs):
        names = [Aircraft.Engine.NUM_ENGINES, Aircraft.Engine.DO_FOO]

        d = {name: {} for name in names}

        return d

    def get_engine_inputs(self, aviary_inputs):
        d = {}
        if aviary_inputs.get_val(Aircraft.Engine.DO_FOO):
            d[Aircraft.Engine.FOO_INPUT_SCALAR0] = {}

            num_engines = aviary_inputs.get_val(Aircraft.Engine.NUM_ENGINES)
            foo_input_vector_size = [2*ne for ne in num_engines]
            d[Aircraft.Engine.FOO_INPUT_VECTOR0] = {"size": foo_input_vector_size}

        return d

class FakeEngineModel(EngineModel):

    def get_engine_options(self, aviary_inputs):
        names = [Aircraft.Engine.NUM_ENGINES, Aircraft.Engine.DO_FOO]
        d = {}
        for name in names:
            d[name] = {}

        return d


    def get_engine_inputs(self, aviary_inputs):
        names = [Aircraft.Engine.REFERENCE_DIAMETER]
        d = {}
        for name in names:
            d[name] = {}

        if aviary_inputs.get_val(Aircraft.Engine.DO_FOO):
            d[Aircraft.Engine.FOO_INPUT_SCALAR0] = {}

            num_engines = self.get_val(Aircraft.Engine.NUM_ENGINES)
            foo_input_vector_size = 2*num_engines
            d[Aircraft.Engine.FOO_INPUT_VECTOR0] = {"size": foo_input_vector_size}

        return d



# def _find_engine_var_in_subsystem(var, aviary_options, all_subsystems):
#     for subsys in all_subsystems:
#         eng_opts = subsys.get_engine_options(aviary_options)
#         if var in eng_opts:
#             return eng_opts[var]

#         eng_inputs = subsys.get_engine_options(aviary_options)
#         if var in eng_inputs:
#             return eng_inputs[var]

#     return {}


# def _find_engine_var_in_engine_model(var, aviary_options, engine_models):
#     var_infos = []
#     for engine_model in engine_models:
#         eng_opts = engine_model.get_engine_options(aviary_options)
#         eng_inputs = engine_model.get_engine_inputs(aviary_options)
#         if var in eng_opts:
#             var_infos.append(eng_opts[var])
#         elif var in eng_inputs:
#             var_infos.append(eng_inputs[var])
#         else:
#             var_infos.append({})

#     return var_infos


class PreprocessPropulsionTest(unittest.TestCase):

    def setUp(self):
        # engine1 = build_engine_deck(engine_1_inputs)
        # engine2 = build_engine_deck(engine_2_inputs)

        options_engine1 = AviaryValues()
        options_engine1.set_val(Aircraft.Engine.NUM_ENGINES, 3)
        engine1 = FakeEngineModel(name="engine1", options=options_engine1, meta_data=ExtendedMetaData)

        options_engine2 = AviaryValues()
        options_engine2.set_val(Aircraft.Engine.NUM_ENGINES, 4)
        engine2 = FakeEngineModel(name="engine2", options=options_engine2, meta_data=ExtendedMetaData)

        self.engine_models = [engine1, engine2]
        # self.prop = CorePropulsionBuilder('core_propulsion', engine_models=self.engine_models)

        # self.mass_flops = CoreMassBuilder('core_mass_flops', code_origin=FLOPS)
        # self.mass_gasp = CoreMassBuilder('core_mass_gasp', code_origin=GASP)

        # self.aero_flops = CoreAerodynamicsBuilder(
        #     'core_aerodynamics_flops', code_origin=FLOPS, tabular=False,
        # )
        # self.aero_gasp = CoreAerodynamicsBuilder(
        #     'core_aerodynamics_gasp', code_origin=GASP, tabular=False,
        # )

        # self.geom_flops = CoreGeometryBuilder(
        #     'core_geometry_flops',
        #     code_origin=FLOPS,
        # )
        # self.geom_gasp = CoreGeometryBuilder(
        #     'core_geometry_gasp',
        #     code_origin=GASP,
        # )

        self.aero = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData)

    def test_empty_aviary_options(self):
        # all_subsystems = [self.prop, self.geom_flops, self.mass_flops, self.aero_flops]
        all_subsystems = [self.aero]

        aviary_options = AviaryValues()
        aviary_options.set_val(Aircraft.Engine.NUM_ENGINES, [3, 4])
        preprocess_propulsion(aviary_options, all_subsystems, self.engine_models, ExtendedMetaData)

        num_engine_models = len(self.engine_models)
        num_engines = aviary_options.get_val(Aircraft.Engine.NUM_ENGINES)
        print(num_engines)

        do_foos = aviary_options.get_val(Aircraft.Engine.DO_FOO)
        self.assertEqual(len(do_foos), num_engine_models)
        self.assertTrue(all(do_foo == True for do_foo in do_foos))
        
        foo_input_scalar0s = aviary_options.get_val(Aircraft.Engine.FOO_INPUT_SCALAR0, units="lbf")
        self.assertEqual(len(foo_input_scalar0s), num_engine_models)
        default_foo = ExtendedMetaData[Aircraft.Engine.FOO_INPUT_SCALAR0]["default_value"]
        self.assertTrue(all(foo == default_foo for foo in foo_input_scalar0s))

        foo_input_vector0s = aviary_options.get_val(Aircraft.Engine.FOO_INPUT_VECTOR0, units="m")
        sz = sum(2*ne for ne in num_engines)
        self.assertEqual(len(foo_input_vector0s), sz)
        default_foo = ExtendedMetaData[Aircraft.Engine.FOO_INPUT_VECTOR0]["default_value"]
        self.assertTrue(all(foo == default_foo for foo in foo_input_vector0s))



if __name__ == '__main__':
    unittest.main()
