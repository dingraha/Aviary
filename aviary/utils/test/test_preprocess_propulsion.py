import unittest

import numpy as np

import aviary.api as av

from aviary.utils.aviary_values import AviaryValues
from aviary.subsystems.aerodynamics.aerodynamics_builder import AerodynamicsBuilderBase
from aviary.subsystems.propulsion.engine_model import EngineModel
from aviary.variable_info.variable_meta_data import _MetaData
from aviary.variable_info.variables import Aircraft as AviaryAircraft

from aviary.utils.preprocessors import preprocess_propulsion
from copy import copy


class Aircraft(AviaryAircraft):
    class Engine(AviaryAircraft.Engine):
        DO_FOO = "aircraft:engine:do_foo"
        FOO_INPUT_SCALAR0 = "aircraft:engine:foo_input_scalar0"
        FOO_INPUT_VECTOR0 = "aircraft:engine:foo_input_vector0"
        BAR_INPUT_VECTOR0 = "aircraft:engine:bar_input_vector0"


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
    default_value=[1.234],
    types=(float, np.ndarray),
    multivalue=True,
    option=False,
    meta_data=ExtendedMetaData
)

av.add_meta_data(
    Aircraft.Engine.BAR_INPUT_VECTOR0,
    units="m**2",
    desc="bar engine vector0",
    default_value=[2.345],
    types=(float, np.ndarray),
    multivalue=True,
    option=False,
    meta_data=ExtendedMetaData
)

class FakeAerodynamicsBuilder(AerodynamicsBuilderBase):
    def __init__(self, name=None, meta_data=None, do_foos=None, num_engines=None, foo_input_scalar0s=None, foo_input_vector0s=None, bar_input_vector0s=None, buggy_foo_input_vector0_size=False, buggy_do_foo_declared_size_length=False, buggy_do_foo_declared_sizes=False):
        if name is None:
            name = 'fake_aerodynamics'

        super().__init__(name=name, meta_data=meta_data)

        self._do_foos = do_foos
        self._num_engines = num_engines
        self._foo_input_scalar0s = foo_input_scalar0s
        self._foo_input_vector0s = foo_input_vector0s
        self._bar_input_vector0s = bar_input_vector0s
        self._buggy_foo_input_vector0_size = buggy_foo_input_vector0_size
        self._buggy_do_foo_declared_size_length = buggy_do_foo_declared_size_length
        self._buggy_do_foo_declared_sizes = buggy_do_foo_declared_sizes

    def get_engine_options(self, aviary_inputs):
        names = [Aircraft.Engine.NUM_ENGINES, Aircraft.Engine.DO_FOO]

        d = {name: {} for name in names}

        if self._do_foos is not None:
            d[Aircraft.Engine.DO_FOO]["val"] = self._do_foos
            if self._buggy_do_foo_declared_size_length:
                d[Aircraft.Engine.DO_FOO]["size"] = [1 for i in range(len(self._do_foos)+1)]
            elif self._buggy_do_foo_declared_sizes:
                d[Aircraft.Engine.DO_FOO]["size"] = [1 for i in range(len(self._do_foos))]
                d[Aircraft.Engine.DO_FOO]["size"][0] = 2

        if self._num_engines is not None:
            d[Aircraft.Engine.NUM_ENGINES]["val"] = self._num_engines

        return d

    def get_engine_inputs(self, aviary_inputs):
        d = {}

        num_engines = aviary_inputs.get_val(Aircraft.Engine.NUM_ENGINES)
        do_foo = aviary_inputs.get_val(Aircraft.Engine.DO_FOO)

        if any(do_foo):
            if self._foo_input_scalar0s is not None:
                d[Aircraft.Engine.FOO_INPUT_SCALAR0] = {"val": self._foo_input_scalar0s}
            else:
                d[Aircraft.Engine.FOO_INPUT_SCALAR0] = {}

            foo_input_vector_size = []
            for i in range(len(num_engines)):
                df = do_foo[i]
                ne = num_engines[i]
                if do_foo[i]:
                    foo_input_vector_size.append(2*num_engines[i])
                    if self._buggy_foo_input_vector0_size:
                        foo_input_vector_size[i] += 1
                else:
                    foo_input_vector_size.append(0)

            d[Aircraft.Engine.FOO_INPUT_VECTOR0] = {"size": foo_input_vector_size}
            if self._foo_input_vector0s is not None:
                d[Aircraft.Engine.FOO_INPUT_VECTOR0]["val"] = self._foo_input_vector0s

        bar_input_vector_size = [3*ne for ne in num_engines]
        d[Aircraft.Engine.BAR_INPUT_VECTOR0] = {"size": bar_input_vector_size}
        if self._bar_input_vector0s is not None:
            d[Aircraft.Engine.BAR_INPUT_VECTOR0]["val"] = self._bar_input_vector0s
            d[Aircraft.Engine.BAR_INPUT_VECTOR0]["units"] = "m**2"


        return d


class FakeEngineModel(EngineModel):

    def __init__(self, name=None, options=None, meta_data=None, buggy_do_foo_declared_size=False, buggy_do_foo_val_size=False):
        if name is None:
            name = "fake_engine"

        super().__init__(name=name, options=options, meta_data=meta_data)

        self._buggy_do_foo_declared_size = buggy_do_foo_declared_size
        self._buggy_do_foo_val_size = buggy_do_foo_val_size

    def get_engine_options(self, aviary_inputs):
        names = [Aircraft.Engine.NUM_ENGINES, Aircraft.Engine.DO_FOO]
        d = {}
        for name in names:
            val, units = self.get_item(name)
            if val is None:
                d[name] = {}
            else:
                d[name] = {"val": val, "units": units}

        if self._buggy_do_foo_declared_size:
            d[Aircraft.Engine.DO_FOO]["size"] = 2

        if self._buggy_do_foo_val_size:
            d[Aircraft.Engine.DO_FOO]["val"] = [True, False]

        return d

    def get_engine_inputs(self, aviary_inputs):
        names = [Aircraft.Engine.REFERENCE_DIAMETER]
        d = {}
        for name in names:
            val, units = self.get_item(name)
            if val is None:
                d[name] = {}
            else:
                d[name] = {"val": val, "units": units}

        # get_item doesn't throw if the thing doesn't exist, unlike get_val.
        do_foo, units = self.get_item(Aircraft.Engine.DO_FOO)
        if do_foo is None:
            # Value isn't in the engine model's AviaryValues (EngineModel.options) attribute.
            # So get the default value from the metadata.
            do_foo = self.meta_data[Aircraft.Engine.DO_FOO]["default_value"]
        if do_foo:
            val, units = self.get_item(Aircraft.Engine.FOO_INPUT_SCALAR0)
            if val is not None:
                d[Aircraft.Engine.FOO_INPUT_SCALAR0] = {"val": val, "units": units}
            else:
                d[Aircraft.Engine.FOO_INPUT_SCALAR0] = {}

            num_engines = self.get_val(Aircraft.Engine.NUM_ENGINES)
            d[Aircraft.Engine.FOO_INPUT_VECTOR0] = {"size": 2*num_engines}

            val, units = self.get_item(Aircraft.Engine.FOO_INPUT_VECTOR0)
            if val is not None:
                d[Aircraft.Engine.FOO_INPUT_VECTOR0]["val"] = val
                d[Aircraft.Engine.FOO_INPUT_VECTOR0]["units"] = units

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

    def test_empty_aviary_options(self):
        options_engine1 = AviaryValues()
        options_engine1.set_val(Aircraft.Engine.NUM_ENGINES, 3)
        engine1 = FakeEngineModel(name="engine1", options=options_engine1, meta_data=ExtendedMetaData)

        options_engine2 = AviaryValues()
        options_engine2.set_val(Aircraft.Engine.NUM_ENGINES, 4)
        engine2 = FakeEngineModel(name="engine2", options=options_engine2, meta_data=ExtendedMetaData)

        engine_models = [engine1, engine2]

        aero = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData)
        all_subsystems = [aero]

        aviary_options = AviaryValues()
        # aviary_options.set_val(Aircraft.Engine.NUM_ENGINES, [3, 4])
        preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)

        num_engine_models = len(engine_models)
        num_engines = aviary_options.get_val(Aircraft.Engine.NUM_ENGINES)
        self.assertTrue(all(ne1 == ne2 for (ne1, ne2) in zip(num_engines, [3, 4])))

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
        default_foo = ExtendedMetaData[Aircraft.Engine.FOO_INPUT_VECTOR0]["default_value"][0]
        self.assertTrue(all(foo == default_foo for foo in foo_input_vector0s))

        bar_input_vector0s = aviary_options.get_val(Aircraft.Engine.BAR_INPUT_VECTOR0, units="m**2")
        sz = sum(3*ne for ne in num_engines)
        self.assertEqual(len(bar_input_vector0s), sz)
        default_bar = ExtendedMetaData[Aircraft.Engine.BAR_INPUT_VECTOR0]["default_value"][0]
        self.assertTrue(all(bar == default_bar for bar in bar_input_vector0s))

    def test_conflicting_aviary_options(self):
        options_engine1 = AviaryValues()
        options_engine1.set_val(Aircraft.Engine.NUM_ENGINES, 3)
        engine1 = FakeEngineModel(name="engine1", options=options_engine1, meta_data=ExtendedMetaData)

        options_engine2 = AviaryValues()
        options_engine2.set_val(Aircraft.Engine.NUM_ENGINES, 4)
        engine2 = FakeEngineModel(name="engine2", options=options_engine2, meta_data=ExtendedMetaData)

        engine_models = [engine1, engine2]

        aero = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData)
        all_subsystems = [aero]

        aviary_options = AviaryValues()
        aviary_options.set_val(Aircraft.Engine.NUM_ENGINES, [3, 5])
        preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)

        num_engine_models = len(engine_models)
        num_engines = aviary_options.get_val(Aircraft.Engine.NUM_ENGINES)
        self.assertTrue(all(ne1 == ne2 for (ne1, ne2) in zip(num_engines, [3, 4])))

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
        default_foo = ExtendedMetaData[Aircraft.Engine.FOO_INPUT_VECTOR0]["default_value"][0]
        self.assertTrue(all(foo == default_foo for foo in foo_input_vector0s))

    def test_only_some_do_foo(self):
        num_engines_expected = [3, 4, 5, 6]
        num_engine_models = len(num_engines_expected)
        do_foos_expected = [False, True, True, False]
        foo_input_scalar0s_expected = np.array([0.1, 0.2, 0.3, 0.4])
        foo_input_vector0s_expected = np.random.rand(sum(2*num_engines_expected[i] for i in range(num_engine_models) if do_foos_expected[i]))
        bar_input_vector0s_expected = np.random.rand(sum(3*num_engines_expected[i] for i in range(num_engine_models)))
        for set_method in ("engine_model", "aero_subsys", "aviary_options"):
            engine_options = [AviaryValues() for i in range(len(num_engines_expected))]
            aero_kwargs = {}
            aviary_options = AviaryValues()
            if set_method == "engine_model":
                idx_var = 0
                for i, engine_opt in enumerate(engine_options):
                    engine_opt.set_val(Aircraft.Engine.NUM_ENGINES, num_engines_expected[i])
                    engine_opt.set_val(Aircraft.Engine.DO_FOO, do_foos_expected[i])
                    if do_foos_expected[i]:
                        engine_opt.set_val(Aircraft.Engine.FOO_INPUT_SCALAR0, foo_input_scalar0s_expected[i], units="lbf")
                        sz = 2*num_engines_expected[i]
                        engine_opt.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_expected[idx_var:idx_var+sz], units="m")
                        idx_var += sz

                # Provide bogus values to the aero subsystem and aviary_options: they should be ignored in favor of the engine model.
                aero_kwargs["num_engines"] = [3*ne for ne in num_engines_expected]
                aero_kwargs["do_foos"] = [not do_foo for do_foo in do_foos_expected]
                # For any engine model with `do_foo == False` the value from the aero model will be stored in aviary_options.
                aero_kwargs["foo_input_scalar0s"] = [8*foo_input_scalar0s_expected[i] if do_foos_expected[i] else foo_input_scalar0s_expected[i] for i in range(num_engine_models)]
                aero_kwargs["foo_input_vector0s"] = foo_input_vector0s_expected + 20.
                aviary_options.set_val(Aircraft.Engine.NUM_ENGINES, [4*ne for ne in num_engines_expected])
                aviary_options.set_val(Aircraft.Engine.DO_FOO, [not do_foo for do_foo in do_foos_expected])
                aviary_options.set_val(Aircraft.Engine.FOO_INPUT_SCALAR0, foo_input_scalar0s_expected - 30.0, units="lbf")
                aviary_options.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_expected - 40.0, units="m")

                # Engine model doesn't care about bar, so have to set it either with the aero model or aviary_options.
                aero_kwargs["bar_input_vector0s"] = bar_input_vector0s_expected
                # Provide bogus values in aviary_options: should be ignored in favor of the aero model.
                aviary_options.set_val(Aircraft.Engine.BAR_INPUT_VECTOR0, bar_input_vector0s_expected + 10.0, units="m**2")
            elif set_method == "aero_subsys":
                aero_kwargs["num_engines"] = num_engines_expected
                aero_kwargs["do_foos"] = do_foos_expected
                aero_kwargs["foo_input_scalar0s"] = foo_input_scalar0s_expected
                aero_kwargs["foo_input_vector0s"] = foo_input_vector0s_expected
                aero_kwargs["bar_input_vector0s"] = bar_input_vector0s_expected

                # Provide bogus values to aviary_options: they should be ignored in favor of the aero subsystem.
                aviary_options.set_val(Aircraft.Engine.NUM_ENGINES, [4*ne for ne in num_engines_expected])
                aviary_options.set_val(Aircraft.Engine.DO_FOO, [not do_foo for do_foo in do_foos_expected])
                aviary_options.set_val(Aircraft.Engine.FOO_INPUT_SCALAR0, foo_input_scalar0s_expected - 30.0, units="lbf")
                aviary_options.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_expected+10.0, units="m")
                aviary_options.set_val(Aircraft.Engine.BAR_INPUT_VECTOR0, bar_input_vector0s_expected + 10.0, units="m**2")
            elif set_method == "aviary_options":
                aviary_options.set_val(Aircraft.Engine.NUM_ENGINES, num_engines_expected)
                aviary_options.set_val(Aircraft.Engine.DO_FOO, do_foos_expected)
                aviary_options.set_val(Aircraft.Engine.FOO_INPUT_SCALAR0, foo_input_scalar0s_expected, units="lbf")
                aviary_options.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_expected, units="m")
                aviary_options.set_val(Aircraft.Engine.BAR_INPUT_VECTOR0, bar_input_vector0s_expected, units="m**2")
            else:
                raise ValueError(f"unknown set_method = {set_method}")

            engine_models = [FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData) for i in range(num_engine_models)]

            aero = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs)
            all_subsystems = [aero]

            num_engine_models = len(engine_models)

            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)

            self.assertEqual(len(aviary_options.get_val(Aircraft.Engine.DO_FOO)), num_engine_models)
            self.assertEqual(aviary_options.get_val(Aircraft.Engine.DO_FOO), do_foos_expected)
            
            # For a scalar input, we always will have `num_engine_models` arguments.
            foo_input_scalar0s = aviary_options.get_val(Aircraft.Engine.FOO_INPUT_SCALAR0, units="lbf")
            self.assertEqual(len(foo_input_scalar0s), num_engine_models)
            self.assertTrue(all(foo == foo_expected for foo, foo_expected in zip(foo_input_scalar0s, foo_input_scalar0s_expected)))

            # For a non-scalar input, we'll only have the number of values necessary for each engine model.
            # So in this case, it will be nothing for the first engine model, and then 2*NUM_ENGINES = 2*4 for the second engine model.
            foo_input_vector0s = aviary_options.get_val(Aircraft.Engine.FOO_INPUT_VECTOR0, units="m")
            sz = sum((2*num_engines_expected[i] for i in range(num_engine_models) if do_foos_expected[i]))
            self.assertEqual(len(foo_input_vector0s), sz)
            self.assertTrue(all(foo == foo_expected for foo, foo_expected in zip(foo_input_vector0s, foo_input_vector0s_expected)))

            bar_input_vector0s = aviary_options.get_val(Aircraft.Engine.BAR_INPUT_VECTOR0, units="m**2")
            sz = sum((3*num_engines_expected[i] for i in range(num_engine_models)))
            self.assertEqual(len(bar_input_vector0s), sz)
            self.assertTrue(all(bar == bar_expected for bar, bar_expected in zip(bar_input_vector0s, bar_input_vector0s_expected)))

            # Should also check that the engine models themselves have the appropriate stuff.
            idx_var = 0
            for i, engine in enumerate(engine_models):
                self.assertEqual(engine.get_val(Aircraft.Engine.DO_FOO, "unitless"), do_foos_expected[i])
                self.assertEqual(engine.get_val(Aircraft.Engine.NUM_ENGINES, "unitless"), num_engines_expected[i])
                if do_foos_expected[i]:
                    foo_input_scalar0 = engine.get_val(Aircraft.Engine.FOO_INPUT_SCALAR0, units="lbf")
                    self.assertTrue(foo_input_scalar0, ExtendedMetaData[Aircraft.Engine.FOO_INPUT_SCALAR0]["default_value"])
                    foo_input_vector0 = engine.get_val(Aircraft.Engine.FOO_INPUT_VECTOR0, units="m")
                    sz = 2*num_engines_expected[i]
                    self.assertEqual(len(foo_input_vector0), sz)
                    self.assertTrue(all(foo == foo_expected for foo, foo_expected in zip(foo_input_vector0, foo_input_vector0s_expected[idx_var:idx_var+sz])))
                    idx_var += sz
                else:
                    self.assertRaises(KeyError, engine.get_val, Aircraft.Engine.FOO_INPUT_SCALAR0, units="lbf")
                    self.assertRaises(KeyError, engine.get_val, Aircraft.Engine.FOO_INPUT_VECTOR0, units="m")

    def test_buggy_subsys_vars(self):
        num_engines_expected = [3, 4, 5, 6]
        num_engine_models = len(num_engines_expected)
        do_foos_expected = [False, True, True, False]
        foo_input_scalar0s_expected = np.array([0.1, 0.2, 0.3, 0.4])
        foo_input_vector0s_expected = np.random.rand(sum(2*num_engines_expected[i] for i in range(num_engine_models) if do_foos_expected[i]))

        engine_options = [AviaryValues() for i in range(len(num_engines_expected))]
        engine_models = [FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData) for i in range(num_engine_models)]

        aero_kwargs0 = {}
        aero_kwargs0["name"] = "aero0"
        aero_kwargs0["num_engines"] = num_engines_expected
        aero_kwargs0["do_foos"] = do_foos_expected
        aero_kwargs0["foo_input_scalar0s"] = foo_input_scalar0s_expected
        aero_kwargs0["foo_input_vector0s"] = foo_input_vector0s_expected

        aero_kwargs1 = {}
        aero_kwargs1["name"] = "aero1"
        aero_kwargs1["num_engines"] = num_engines_expected
        # Add additional value, should throw an error complaining about the size.
        do_foos_bogus = copy(do_foos_expected)
        do_foos_bogus.append(False)
        aero_kwargs1["do_foos"] = do_foos_bogus
        aero_kwargs1["foo_input_scalar0s"] = foo_input_scalar0s_expected
        aero_kwargs1["foo_input_vector0s"] = foo_input_vector0s_expected

        aero0 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs0)
        aero1 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs1)

        all_subsystems = [aero0, aero1]

        aviary_options = AviaryValues()

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        self.assertEqual(str(cm.exception), f"variable {var} in Model <{aero1.name}> does not have expected size {len(do_foos_expected)}")

        aero_kwargs0 = {}
        aero_kwargs0["name"] = "aero0"
        aero_kwargs0["num_engines"] = num_engines_expected
        aero_kwargs0["do_foos"] = do_foos_expected
        aero_kwargs0["foo_input_scalar0s"] = foo_input_scalar0s_expected
        aero_kwargs0["foo_input_vector0s"] = foo_input_vector0s_expected

        aero_kwargs1 = {}
        aero_kwargs1["name"] = "aero1"
        aero_kwargs1["num_engines"] = num_engines_expected
        # Change one of the value, should throw an error complaining about non-identical values.
        do_foos_bogus = copy(do_foos_expected)
        do_foos_bogus[0] = not do_foos_expected[0]
        aero_kwargs1["do_foos"] = do_foos_bogus
        aero_kwargs1["foo_input_scalar0s"] = foo_input_scalar0s_expected
        aero_kwargs1["foo_input_vector0s"] = foo_input_vector0s_expected

        aero0 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs0)
        aero1 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs1)

        all_subsystems = [aero0, aero1]

        aviary_options = AviaryValues()

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        subsys_names = [x.name for x in all_subsystems]
        self.assertEqual(str(cm.exception), f"non-identical values for variable {var} found in multiple subsystems: {subsys_names}")

        aero_kwargs0 = {}
        aero_kwargs0["name"] = "aero0"
        aero_kwargs0["num_engines"] = num_engines_expected
        aero_kwargs0["do_foos"] = do_foos_expected
        aero_kwargs0["foo_input_scalar0s"] = foo_input_scalar0s_expected
        aero_kwargs0["foo_input_vector0s"] = foo_input_vector0s_expected

        aero_kwargs1 = {}
        aero_kwargs1["name"] = "aero1"
        aero_kwargs1["num_engines"] = num_engines_expected
        aero_kwargs1["do_foos"] = do_foos_expected
        aero_kwargs1["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs1["foo_input_vector0s"] = foo_input_vector0s_expected
        aero_kwargs1["buggy_foo_input_vector0_size"] = True

        aero0 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs0)
        aero1 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs1)

        all_subsystems = [aero0, aero1]

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.FOO_INPUT_VECTOR0
        subsys_names = [x.name for x in all_subsystems]
        self.assertEqual(str(cm.exception), f"non-identical sizes for variable {var} found in multiple subsystems: {subsys_names}")

        aero_kwargs0 = {}
        aero_kwargs0["name"] = "aero0"
        aero_kwargs0["num_engines"] = num_engines_expected
        # aero_kwargs0["do_foos"] = do_foos_expected
        aero_kwargs0["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs0["foo_input_vector0s"] = foo_input_vector0s_expected

        aero_kwargs1 = {}
        aero_kwargs1["name"] = "aero1"
        aero_kwargs1["num_engines"] = num_engines_expected
        # aero_kwargs1["do_foos"] = do_foos_expected
        aero_kwargs1["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs1["foo_input_vector0s"] = foo_input_vector0s_expected

        aero0 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs0)
        aero1 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs1)

        all_subsystems = [aero0, aero1]

        # Set incorrect size for a scalar value in aviary_options.
        aviary_options = AviaryValues()
        # foo_input_vector0s_bogus = np.append(foo_input_vector0s_expected, 8.0)
        do_foos_bogus = copy(do_foos_expected)
        do_foos_bogus.append(True)
        aviary_options.set_val(Aircraft.Engine.DO_FOO, do_foos_bogus)

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        self.assertEqual(str(cm.exception), f"incorrect number of values found for variable {var} in aviary_options: expected {num_engine_models} values (one per engine model), but found {len(do_foos_bogus)}")

        aero_kwargs0 = {}
        aero_kwargs0["name"] = "aero0"
        aero_kwargs0["num_engines"] = num_engines_expected
        aero_kwargs0["do_foos"] = do_foos_expected
        aero_kwargs0["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs0["foo_input_vector0s"] = foo_input_vector0s_expected

        aero_kwargs1 = {}
        aero_kwargs1["name"] = "aero1"
        aero_kwargs1["num_engines"] = num_engines_expected
        aero_kwargs1["do_foos"] = do_foos_expected
        aero_kwargs1["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs1["foo_input_vector0s"] = foo_input_vector0s_expected

        aero0 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs0)
        aero1 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs1)

        all_subsystems = [aero0, aero1]

        # Set incorrect size for a vector value in aviary_options.
        aviary_options = AviaryValues()
        foo_input_vector0s_bogus = np.append(foo_input_vector0s_expected, 8.0)
        aviary_options.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_bogus, units="m")

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.FOO_INPUT_VECTOR0
        sz_expected = [2*num_engines_expected[i] if do_foos_expected[i] else 0 for i in range(num_engine_models)]
        self.assertEqual(str(cm.exception), f"size {foo_input_vector0s_bogus.size} of variable {var} found in aviary_options incompatible with sizes {sz_expected} found in non-engine subsystems")

        aero_kwargs0 = {}
        aero_kwargs0["name"] = "aero0"
        aero_kwargs0["num_engines"] = num_engines_expected
        aero_kwargs0["do_foos"] = do_foos_expected
        aero_kwargs0["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs0["foo_input_vector0s"] = foo_input_vector0s_expected

        aero_kwargs1 = {}
        aero_kwargs1["name"] = "aero1"
        aero_kwargs1["num_engines"] = num_engines_expected
        aero_kwargs1["do_foos"] = do_foos_expected
        aero_kwargs1["foo_input_scalar0s"] = foo_input_scalar0s_expected
        aero_kwargs1["buggy_do_foo_declared_size_length"] = True
        # aero_kwargs1["foo_input_vector0s"] = foo_input_vector0s_expected

        aero0 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs0)
        aero1 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs1)

        all_subsystems = [aero0, aero1]

        aviary_options = AviaryValues()

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        self.assertEqual(str(cm.exception), f"size declared for variable {var} by subsystem <{aero1.name}> should be a list of length {num_engine_models}, but has length {num_engine_models+1}")

        aero_kwargs0 = {}
        aero_kwargs0["name"] = "aero0"
        aero_kwargs0["num_engines"] = num_engines_expected
        aero_kwargs0["do_foos"] = do_foos_expected
        aero_kwargs0["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs0["foo_input_vector0s"] = foo_input_vector0s_expected

        aero_kwargs1 = {}
        aero_kwargs1["name"] = "aero1"
        aero_kwargs1["num_engines"] = num_engines_expected
        aero_kwargs1["do_foos"] = do_foos_expected
        aero_kwargs1["foo_input_scalar0s"] = foo_input_scalar0s_expected
        # aero_kwargs1["buggy_do_foo_declared_size_length"] = True
        aero_kwargs1["buggy_do_foo_declared_sizes"] = True
        # aero_kwargs1["foo_input_vector0s"] = foo_input_vector0s_expected

        aero0 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs0)
        aero1 = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs1)

        all_subsystems = [aero0, aero1]

        aviary_options = AviaryValues()

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        self.assertEqual(str(cm.exception), f"non-multidimensional variable {var} has at least one non-0 or non-1 size declared by subsystem <{aero1.name}>")

    def test_buggy_engine_vars(self):
        num_engines_expected = [3, 4, 5, 6]
        num_engine_models = len(num_engines_expected)
        do_foos_expected = [False, True, True, False]
        foo_input_scalar0s_expected = np.array([0.1, 0.2, 0.3, 0.4])
        foo_input_vector0s_expected = np.random.rand(sum(2*num_engines_expected[i] for i in range(num_engine_models) if do_foos_expected[i]))
        bar_input_vector0s_expected = np.random.rand(sum(3*num_engines_expected[i] for i in range(num_engine_models)))

        engine_options = [AviaryValues() for i in range(len(num_engines_expected))]
        aero_kwargs = {}
        aviary_options = AviaryValues()
        idx_var = 0
        for i, engine_opt in enumerate(engine_options):
            engine_opt.set_val(Aircraft.Engine.NUM_ENGINES, num_engines_expected[i])
            engine_opt.set_val(Aircraft.Engine.DO_FOO, do_foos_expected[i])
            if do_foos_expected[i]:
                engine_opt.set_val(Aircraft.Engine.FOO_INPUT_SCALAR0, foo_input_scalar0s_expected[i], units="lbf")
                sz = 2*num_engines_expected[i]
                engine_opt.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_expected[idx_var:idx_var+sz], units="m")
                idx_var += sz

                aero_kwargs["num_engines"] = num_engines_expected
                aero_kwargs["do_foos"] = do_foos_expected
                # For any engine model with `do_foo == False` the value from the aero model will be stored in aviary_options.
                aero_kwargs["foo_input_scalar0s"] = foo_input_scalar0s_expected
                aero_kwargs["foo_input_vector0s"] = foo_input_vector0s_expected

        engine_models = [FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData) for i in range(num_engine_models-1)]
        i = num_engine_models - 1
        engine_models.append(FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData, buggy_do_foo_declared_size=True))

        aero = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs)
        all_subsystems = [aero]

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        buggy_sz = 2
        self.assertEqual(str(cm.exception), f"declared size {buggy_sz} for variable {var} in EngineModel <{engine_models[-1].name}> does not match expected size 1")

        engine_models = [FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData) for i in range(num_engine_models-1)]
        i = num_engine_models - 1
        engine_models.append(FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData, buggy_do_foo_val_size=True))

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        self.assertEqual(str(cm.exception), f"variable {var} in EngineModel <{engine_models[-1].name}> does not have expected size 1, but has size 2")

        engine_options = [AviaryValues() for i in range(len(num_engines_expected))]
        do_foos_buggy = do_foos_expected[:-1]
        aviary_options = AviaryValues()
        aviary_options.set_val(Aircraft.Engine.DO_FOO, do_foos_buggy)
        aero_kwargs = {}
        idx_var = 0
        for i, engine_opt in enumerate(engine_options):
            engine_opt.set_val(Aircraft.Engine.NUM_ENGINES, num_engines_expected[i])
            engine_opt.set_val(Aircraft.Engine.DO_FOO, do_foos_expected[i])
            if do_foos_expected[i]:
                engine_opt.set_val(Aircraft.Engine.FOO_INPUT_SCALAR0, foo_input_scalar0s_expected[i], units="lbf")
                sz = 2*num_engines_expected[i]
                engine_opt.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_expected[idx_var:idx_var+sz], units="m")
                idx_var += sz

                aero_kwargs["num_engines"] = num_engines_expected
                aero_kwargs["do_foos"] = do_foos_expected
                # For any engine model with `do_foo == False` the value from the aero model will be stored in aviary_options.
                aero_kwargs["foo_input_scalar0s"] = foo_input_scalar0s_expected
                aero_kwargs["foo_input_vector0s"] = foo_input_vector0s_expected

        engine_models = [FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData) for i in range(num_engine_models-1)]
        i = num_engine_models - 1
        engine_models.append(FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData, buggy_do_foo_declared_size=True))

        aero = FakeAerodynamicsBuilder(meta_data=ExtendedMetaData, **aero_kwargs)
        all_subsystems = [aero]

        engine_models = [FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData) for i in range(num_engine_models)]

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.DO_FOO
        self.assertEqual(str(cm.exception), f"value for variable {var} taken from aviary_options argument has too-small size")

        engine_options = [AviaryValues() for i in range(len(num_engines_expected))]
        aviary_options = AviaryValues()
        foo_input_vector0s_buggy = foo_input_vector0s_expected[:-1]
        aviary_options.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_buggy, units="m")
        aero_kwargs = {}
        idx_var = 0
        for i, engine_opt in enumerate(engine_options):
            engine_opt.set_val(Aircraft.Engine.NUM_ENGINES, num_engines_expected[i])
            engine_opt.set_val(Aircraft.Engine.DO_FOO, do_foos_expected[i])
            if do_foos_expected[i]:
                engine_opt.set_val(Aircraft.Engine.FOO_INPUT_SCALAR0, foo_input_scalar0s_expected[i], units="lbf")
                # sz = 2*num_engines_expected[i]
                # engine_opt.set_val(Aircraft.Engine.FOO_INPUT_VECTOR0, foo_input_vector0s_expected[idx_var:idx_var+sz], units="m")
                # idx_var += sz

                aero_kwargs["num_engines"] = num_engines_expected
                aero_kwargs["do_foos"] = do_foos_expected
                # For any engine model with `do_foo == False` the value from the aero model will be stored in aviary_options.
                aero_kwargs["foo_input_scalar0s"] = foo_input_scalar0s_expected
                # aero_kwargs["foo_input_vector0s"] = foo_input_vector0s_expected

        all_subsystems = []

        engine_models = [FakeEngineModel(name=f"engine{i}", options=engine_options[i], meta_data=ExtendedMetaData) for i in range(num_engine_models)]

        with self.assertRaises(ValueError) as cm:
            preprocess_propulsion(aviary_options, all_subsystems, engine_models, ExtendedMetaData)
        var = Aircraft.Engine.FOO_INPUT_VECTOR0
        self.assertEqual(str(cm.exception), f"value for variable {var} taken from aviary_options argument has too-small size")


if __name__ == '__main__':
    unittest.main()
