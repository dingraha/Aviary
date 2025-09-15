"""
Preprocessors are utility functions that handle issues with Aviary inputs before model
setup and execution. These tasks include consistency checking between related variables,.

"""

import warnings

import numpy as np

from openmdao.utils.units import convert_units

from aviary.utils.aviary_values import AviaryValues
from aviary.utils.named_values import get_keys
from aviary.utils.test_utils.variable_test import get_names_from_hierarchy
from aviary.utils.utils import isiterable
from aviary.variable_info.enums import LegacyCode, ProblemType, Verbosity
from aviary.variable_info.variable_meta_data import _MetaData
from aviary.variable_info.variables import Aircraft, Mission, Settings


# TODO document what kwargs are used, and by which preprocessors in docstring?
def preprocess_options(aviary_options: AviaryValues, all_subsystems, meta_data=_MetaData, verbosity=None, **kwargs):
    """
    Run all preprocessors on provided AviaryValues object.

    Parameters
    ----------
    aviary_options : AviaryValues
        Options to be updated

    all_subsystems : list of subsystems
        subsystems used to determine engine-related variables needed

    meta_data : dict
        Variable metadata being used with this set of aviary_options
    """
    try:
        engine_models = kwargs['engine_models']
    except KeyError:
        engine_models = None

    if verbosity is None:
        if Settings.VERBOSITY in aviary_options:
            verbosity = aviary_options.get_val(Settings.VERBOSITY)
        else:
            verbosity = meta_data[Settings.VERBOSITY]['default_value']
            aviary_options.set_val(Settings.VERBOSITY, verbosity)

    preprocess_crewpayload(aviary_options, meta_data, verbosity)
    if not engine_models is None:
        preprocess_propulsion(aviary_options, all_subsystems, engine_models, meta_data, verbosity)


def remove_preprocessed_options(aviary_options):
    """
    Remove options whose values will be computed in the preprocessors.

    Parameters
    ----------
    aviary_options : AviaryValues
        Options to be updated
    """
    pre_opt = [
        Aircraft.CrewPayload.NUM_FLIGHT_CREW,
        Aircraft.CrewPayload.NUM_FLIGHT_ATTENDANTS,
        Aircraft.CrewPayload.NUM_GALLEY_CREW,
        Aircraft.CrewPayload.BAGGAGE_MASS_PER_PASSENGER,
    ]

    for option in pre_opt:
        aviary_options.delete(option)


def preprocess_crewpayload(aviary_options: AviaryValues, meta_data=_MetaData, verbosity=None):
    """
    Calculates option values that are derived from other options, and are not direct inputs.
    This function modifies the entries in the supplied collection, and for convenience also
    returns the modified collection.
    """
    if verbosity is not None:
        # compatibility with being passed int for verbosity
        verbosity = Verbosity(verbosity)
    else:
        verbosity = aviary_options.get_val(Settings.VERBOSITY)

    # Some tests, but not all, do not correctly set default values
    # # so we need to ensure all these values are available.

    for key in (
        Aircraft.CrewPayload.NUM_PASSENGERS,
        Aircraft.CrewPayload.NUM_FIRST_CLASS,
        Aircraft.CrewPayload.NUM_BUSINESS_CLASS,
        Aircraft.CrewPayload.NUM_TOURIST_CLASS,
        Aircraft.CrewPayload.Design.NUM_PASSENGERS,
        Aircraft.CrewPayload.Design.NUM_FIRST_CLASS,
        Aircraft.CrewPayload.Design.NUM_BUSINESS_CLASS,
        Aircraft.CrewPayload.Design.NUM_TOURIST_CLASS,
    ):
        if key not in aviary_options:
            aviary_options.set_val(key, meta_data[key]['default_value'])

    # Sum passenger Counts for later checks and assignments
    passenger_count = 0
    for key in (
        Aircraft.CrewPayload.NUM_FIRST_CLASS,
        Aircraft.CrewPayload.NUM_BUSINESS_CLASS,
        Aircraft.CrewPayload.NUM_TOURIST_CLASS,
    ):
        passenger_count += aviary_options.get_val(key)
    design_passenger_count = 0
    for key in (
        Aircraft.CrewPayload.Design.NUM_FIRST_CLASS,
        Aircraft.CrewPayload.Design.NUM_BUSINESS_CLASS,
        Aircraft.CrewPayload.Design.NUM_TOURIST_CLASS,
    ):
        design_passenger_count += aviary_options.get_val(key)

    # Create summary value (num_pax) if it was not assigned by the user
    # or if it was set to it's default value of zero
    if passenger_count != 0 and aviary_options.get_val(Aircraft.CrewPayload.NUM_PASSENGERS) == 0:
        aviary_options.set_val(Aircraft.CrewPayload.NUM_PASSENGERS, passenger_count)
        if verbosity >= Verbosity.VERBOSE:
            warnings.warn(
                'User has specified supporting values for NUM_PASSENGERS but has left '
                'NUM_PASSENGERS=0. Replacing NUM_PASSENGERS with passenger_count.'
            )
    if (
        design_passenger_count != 0
        and aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS) == 0
    ):
        aviary_options.set_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS, design_passenger_count)
        if verbosity >= Verbosity.VERBOSE:
            warnings.warn(
                'User has specified supporting values for Design.NUM_PASSENGERS but has '
                'left Design.NUM_PASSENGERS=0. Replacing Design.NUM_PASSENGERS with '
                'design_passenger_count.'
            )

    num_pax = aviary_options.get_val(Aircraft.CrewPayload.NUM_PASSENGERS)
    design_num_pax = aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS)

    # TODO these don't have to be errors, we can recover in some cases, for example
    # defaulting to all economy class if passenger seat info is not provided. See the
    # engine count checks for an example of this.
    # Check summary data against individual data if individual data was entered
    if passenger_count != 0 and num_pax != passenger_count:
        raise UserWarning(
            'NUM_PASSENGERS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.NUM_PASSENGERS)}) does not '
            'equal the sum of first class + business class + tourist class passengers '
            f'(total of {passenger_count}).'
        )
    if design_passenger_count != 0 and design_num_pax != design_passenger_count:
        raise UserWarning(
            'Design.NUM_PASSENGERS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS)}) '
            'does not equal the sum of design first class + business class + tourist '
            f'class passengers (total of {design_passenger_count}).'
        )

    # Fail if incorrect data sets were provided:
    # have you give us enough info to determine where people were sitting vs. designed seats
    if num_pax != 0 and design_passenger_count != 0 and passenger_count == 0:
        raise UserWarning(
            'The user has specified CrewPayload.NUM_PASSENGERS, and how many of what '
            'types of seats are on the aircraft. However, the user has not specified '
            'where those passengers are sitting. User must specify '
            'CrewPayload.FIRST_CLASS, CrewPayload.NUM_BUSINESS_CLASS, NUM_TOURIST_CLASS '
            'in aviary_values.'
        )
        # where are the people sitting? is first class full? We know how many seats are in each class.
    if design_num_pax != 0 and passenger_count != 0 and design_passenger_count == 0:
        raise UserWarning(
            'The user has specified Design.NUM_PASSENGERS, and has specified how many '
            'people are sitting in each class of seats. However, the user has not '
            'specified how many seats of each class exist in the aircraft. User must '
            'specify Design.FIRST_CLASS, Design.NUM_BUSINESS_CLASS, '
            'Design.NUM_TOURIST_CLASS in aviary_values.'
        )
        # we don't know which classes this aircraft has been design for. How many 1st class seats are there?

    # Copy data over if only one set of data exists
    # User has given detailed values for 1TB as flow and NO design values at all
    if passenger_count != 0 and design_num_pax == 0 and design_passenger_count == 0:
        if verbosity >= Verbosity.VERBOSE:
            warnings.warn(
                'User has not input design passengers data. Assuming design is equal to '
                'as-flow passenger data.'
            )
        aviary_options.set_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS, passenger_count)
        aviary_options.set_val(
            Aircraft.CrewPayload.Design.NUM_FIRST_CLASS,
            aviary_options.get_val(Aircraft.CrewPayload.NUM_FIRST_CLASS),
        )
        aviary_options.set_val(
            Aircraft.CrewPayload.Design.NUM_BUSINESS_CLASS,
            aviary_options.get_val(Aircraft.CrewPayload.NUM_BUSINESS_CLASS),
        )
        aviary_options.set_val(
            Aircraft.CrewPayload.Design.NUM_TOURIST_CLASS,
            aviary_options.get_val(Aircraft.CrewPayload.NUM_TOURIST_CLASS),
        )
    # user has not supplied detailed information on design but has supplied summary information on passengers
    elif num_pax != 0 and design_num_pax == 0:
        if verbosity >= Verbosity.VERBOSE:
            warnings.warn(
                'User has specified as-flown NUM_PASSENGERS but not how many passengers '
                'the aircraft was designed for in Design.NUM_PASSENGERS. Assuming they '
                'are equal.'
            )
        aviary_options.set_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS, num_pax)
    elif design_passenger_count != 0 and num_pax == 0 and passenger_count == 0:
        if verbosity >= Verbosity.VERBOSE:
            warnings.warn(
                'User has specified Design.NUM_* passenger values but CrewPyaload.NUM_* '
                'category has been left blank or set to zero. Assuming they are equal '
                'to maintain backwards compatibility with converted GASP and FLOPS. '
                'If you intended to have no passengers on this flight, set '
                'Aircraft.CrewPayload.TOTAL_PAYLOAD_MASS to zero in aviary_values.'
            )
        aviary_options.set_val(Aircraft.CrewPayload.NUM_PASSENGERS, design_passenger_count)
        aviary_options.set_val(
            Aircraft.CrewPayload.NUM_FIRST_CLASS,
            aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_FIRST_CLASS),
        )
        aviary_options.set_val(
            Aircraft.CrewPayload.NUM_BUSINESS_CLASS,
            aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_BUSINESS_CLASS),
        )
        aviary_options.set_val(
            Aircraft.CrewPayload.NUM_TOURIST_CLASS,
            aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_TOURIST_CLASS),
        )
    # user has not supplied detailed information on design but has supplied summary information on passengers
    elif design_num_pax != 0 and num_pax == 0:
        if verbosity >= Verbosity.VERBOSE:
            warnings.warn(
                'User has specified Design.NUM_PASSENGERS but '
                'CrewPayload.NUM_PASSENGERS has been left blank or set to zero. '
                'Assuming they are equal to maintain backwards compatibility with '
                'converted GASP and FLOPS files. If you intended to have no passengers '
                'on this flight, set Aircraft.CrewPayload.TOTAL_PAYLOAD_MASS to zero in '
                'aviary_values'
            )
        aviary_options.set_val(Aircraft.CrewPayload.NUM_PASSENGERS, design_num_pax)

    # Perform checks on the final data tables to ensure Design is always larger then As-Flown
    if aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_FIRST_CLASS) < aviary_options.get_val(
        Aircraft.CrewPayload.NUM_FIRST_CLASS
    ):
        raise UserWarning(
            'NUM_FIRST_CLASS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.NUM_FIRST_CLASS)}) is larger '
            'than the number of seats set by Design.NUM_FIRST_CLASS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_FIRST_CLASS)})'
        )
    if aviary_options.get_val(
        Aircraft.CrewPayload.Design.NUM_BUSINESS_CLASS
    ) < aviary_options.get_val(Aircraft.CrewPayload.NUM_BUSINESS_CLASS):
        raise UserWarning(
            'NUM_BUSINESS_CLASS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.NUM_BUSINESS_CLASS)}) is '
            'larger than the number of seats set by Design.NUM_BUSINESS_CLASS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_BUSINESS_CLASS)})'
        )
    if aviary_options.get_val(
        Aircraft.CrewPayload.Design.NUM_TOURIST_CLASS
    ) < aviary_options.get_val(Aircraft.CrewPayload.NUM_TOURIST_CLASS):
        raise UserWarning(
            'NUM_TOURIST_CLASS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.NUM_TOURIST_CLASS)}) is '
            'larger than the number of seats set by Design.NUM_TOURIST_CLASS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_TOURIST_CLASS)})'
        )
    if aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS) < aviary_options.get_val(
        Aircraft.CrewPayload.NUM_PASSENGERS
    ):
        raise UserWarning(
            'NUM_PASSENGERS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.NUM_PASSENGERS)}) is larger '
            'than the number of seats set by Design.NUM_PASSENGERS ('
            f'{aviary_options.get_val(Aircraft.CrewPayload.Design.NUM_PASSENGERS)})'
        )

    # Check and process cargo variables - confirm mass method
    if Settings.MASS_METHOD in aviary_options:
        mass_method = aviary_options.get_val(Settings.MASS_METHOD)
    else:
        raise UserWarning('MASS_METHOD not specified. Cannot preprocess cargo inputs.')

    # Process GASP based cargo variables
    if mass_method == LegacyCode.GASP:
        try:
            cargo = aviary_options.get_val(Aircraft.CrewPayload.CARGO_MASS, 'lbm')
        except KeyError:
            cargo = None
        try:
            max_cargo = aviary_options.get_val(Aircraft.CrewPayload.Design.MAX_CARGO_MASS, 'lbm')
        except KeyError:
            max_cargo = None
        try:
            des_cargo = aviary_options.get_val(Aircraft.CrewPayload.Design.CARGO_MASS, 'lbm')
        except KeyError:
            des_cargo = None

        if Settings.PROBLEM_TYPE in aviary_options:
            problem_type = aviary_options.get_val(Settings.PROBLEM_TYPE)
        else:
            problem_type = ProblemType.SIZING

        if cargo is not None:
            if max_cargo is not None:
                if des_cargo is not None:
                    if problem_type == ProblemType.SIZING and cargo != des_cargo:
                        # user has set all three check if self consistent
                        cargo = des_cargo
                        if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                            warnings.warn(
                                f'Aircraft.CrewPayload.CARGO_MASS ({cargo}) does '
                                'not equal Aircraft.CrewPayload.Design.CARGO_MASS '
                                f'({des_cargo}) for SIZING mission. Setting as-flown '
                                'CARGO_MASS equal to Design.CARGO_MASS '
                                f'({des_cargo})'
                            )
                else:
                    # user has set cargo & max: assume des = max
                    des_cargo = max_cargo
                    if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                        warnings.warn(
                            'Aircraft.CrewPayload.Design.CARGO_MASS missing, '
                            'assume Design.CARGO_MASS = Design.MAX_CARGO_MASS '
                            f'({max_cargo})'
                        )
            elif des_cargo is not None:
                # user has set cargo & des: assume max = des
                max_cargo = des_cargo
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                    warnings.warn(
                        'Aircraft.CrewPayload.Design.MAX_CARGO_MASS is missing, '
                        'assuming Design.MAX_CARGO_MASS equals Design.CARGO_MASS '
                        f'({des_cargo})'
                    )
            else:
                # user has set cargo only: assume intention to set max only for backwards compatibility.
                # TODO we eventually want to fix these and have des & flown cargo = max cargo
                #      that fix will possibly require updating fortran_to_aviary
                max_cargo = cargo
                cargo = des_cargo = 0
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                    warnings.warn(
                        'As-flown cargo mass was specified but design cargo mass and '
                        'max cargo mass were not. To maintain backwards-compatibility '
                        f'with converted GASP files, setting max cargo mass to {cargo} '
                        'and maximum and design cargo masses to zero.'
                    )

        elif max_cargo is not None:
            if des_cargo is not None:
                # user has set max & des: assume flown = 0
                cargo = 0
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG:
                    warnings.warn(
                        'Aircraft.CrewPayload.CARGO_MASS is missing, assuming CARGO_MASS = 0'
                    )
            else:
                # user has set max only: assume flown = des = 0
                cargo = des_cargo = 0
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG:
                    warnings.warn(
                        'Aircraft.CrewPayload.CARGO_MASS and '
                        'Aircraft.CrewPayload.Design.CARGO_MASS missing, assume '
                        'CARGO_MASS and Design.CARGO_MASS = 0. No Cargo is flown '
                        'on any mission.'
                    )

        elif des_cargo is not None:
            # user has only input des: assume max = des and flown = 0
            max_cargo = des_cargo
            cargo = 0
            if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG:
                warnings.warn(
                    'Aircraft.CrewPayload.CARGO_MASS and '
                    'Aircraft.CrewPayload.Design.MAX_CARGO_MASS missing, assume '
                    'CARGO_MASS = 0 and Design.MAX_CARGO_MASS = Design.CARGO_MASS '
                    f'({des_cargo}).'
                )

        else:
            # user has input no cargo information
            cargo = max_cargo = des_cargo = 0
            if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG:
                warnings.warn(
                    'No CARGO variables detected, assume CARGO_MASS, '
                    'Design.MAX_CARGO_MASS, and Design.CARGO_MASS equal to 0.'
                )

        # check for potential cargo errors:
        if cargo > des_cargo:
            if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG:
                warnings.warn(
                    f'As-flown cargo ({cargo}) is greater than design cargo ({des_cargo})'
                )

        if cargo > max_cargo or des_cargo > max_cargo:
            raise UserWarning(
                f'Aircraft.CrewPayload.CARGO_MASS ({cargo}) and/or '
                f'Aircraft.CrewPayload.Design.CARGO_MASS ({des_cargo}) is greater '
                f'than Aircraft.CrewPayload.Design.MAX_CARGO_MASS ({max_cargo})'
            )

        # calculate passenger mass with bags based on user inputs.
        try:
            pax_mass_with_bag = aviary_options.get_val(
                Aircraft.CrewPayload.PASSENGER_MASS_WITH_BAGS, 'lbm'
            )
        except KeyError:
            pax_mass = aviary_options.get_val(Aircraft.CrewPayload.MASS_PER_PASSENGER, 'lbm')
            bag_mass = aviary_options.get_val(
                Aircraft.CrewPayload.BAGGAGE_MASS_PER_PASSENGER, 'lbm'
            )
            pax_mass_with_bag = pax_mass + bag_mass
            aviary_options.set_val(
                Aircraft.CrewPayload.PASSENGER_MASS_WITH_BAGS, pax_mass_with_bag, 'lbm'
            )

        # calculate and check total payload
        # NOTE this is only used for error messaging the calculations for analysis are subsystems/mass/gasp_based
        design_passenger_payload_mass = design_num_pax * pax_mass_with_bag
        des_payload = design_passenger_payload_mass + des_cargo
        num_pax = aviary_options.get_val(Aircraft.CrewPayload.NUM_PASSENGERS)
        as_flown_passenger_payload_mass = num_pax * pax_mass_with_bag
        as_flown_payload = as_flown_passenger_payload_mass + cargo
        if as_flown_payload > des_payload and verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
            warnings.warn(
                f'As-flown payload ({as_flown_payload}) is greater than design payload '
                f'({des_payload}). The aircraft will be undersized for this payload!'
            )

        # set assumed cargo mass variables:
        aviary_options.set_val(Aircraft.CrewPayload.CARGO_MASS, cargo, 'lbm')
        aviary_options.set_val(Aircraft.CrewPayload.Design.MAX_CARGO_MASS, max_cargo, 'lbm')
        aviary_options.set_val(Aircraft.CrewPayload.Design.CARGO_MASS, des_cargo, 'lbm')

    if Aircraft.CrewPayload.NUM_FLIGHT_ATTENDANTS not in aviary_options:
        flight_attendants_count = 0  # assume no passengers

        if 0 < passenger_count:
            if passenger_count < 51:
                flight_attendants_count = 1

            else:
                flight_attendants_count = passenger_count // 40 + 1

        aviary_options.set_val(Aircraft.CrewPayload.NUM_FLIGHT_ATTENDANTS, flight_attendants_count)

    if Aircraft.CrewPayload.NUM_GALLEY_CREW not in aviary_options:
        galley_crew_count = 0  # assume no passengers

        if 150 < passenger_count:
            galley_crew_count = passenger_count // 250 + 1

        aviary_options.set_val(Aircraft.CrewPayload.NUM_GALLEY_CREW, galley_crew_count)

    if Aircraft.CrewPayload.NUM_FLIGHT_CREW not in aviary_options:
        flight_crew_count = 3

        if passenger_count < 151:
            flight_crew_count = 2

        aviary_options.set_val(Aircraft.CrewPayload.NUM_FLIGHT_CREW, flight_crew_count)

    if (
        Aircraft.CrewPayload.BAGGAGE_MASS_PER_PASSENGER not in aviary_options
        and Mission.Design.RANGE in aviary_options
    ):
        design_range = aviary_options.get_val(Mission.Design.RANGE, 'nmi')

        if design_range <= 900.0:
            baggage_mass_per_pax = 35.0
        elif design_range <= 2900.0:
            baggage_mass_per_pax = 40.0
        else:
            baggage_mass_per_pax = 44.0

        aviary_options.set_val(
            Aircraft.CrewPayload.BAGGAGE_MASS_PER_PASSENGER,
            val=baggage_mass_per_pax,
            units='lbm',
        )

    return aviary_options

def _reconcile_engine_vars(aviary_options, all_subsystems, engine_models, meta_data, do_options, verbosity):

    ##############################
    # Vectorize Engine Variables #
    ##############################
    # Only vectorize variables user has defined in some way or engine model has calculated
    # Combine aviary_options and all engine options into single AviaryValues
    # It is assumed that all EngineModels are up-to-date at this point and will NOT
    # be changed later on (otherwise preprocess_propulsion must be run again)
    num_engine_type = len(engine_models)
    # Default size for a non-engine subsystem is a length-num_engine_models list of 1s.
    sz_default_subsys = [1 for _ in range(num_engine_type)]

    # complete_options_list = AviaryValues(aviary_options)
    # for engine in engine_models:
    #     # complete_options_list.update(engine.options)
    #     d = {k: (v["val"], v["units"]) for k, v in engine.get_engine_options().items()}
    #     complete_options_list.update(**d)
    #     d = {k: (v["val"], v["units"]) for k, v in engine.get_engine_inputs().items()}
    #     complete_options_list.update(**d)

    # update_options_set = set(get_keys(aviary_options))
    update_set = set()
    for engine in engine_models:
        if do_options:
            update_set.update(engine.get_engine_options(aviary_options).keys())
        else:
            update_set.update(engine.get_engine_inputs(aviary_options).keys())
    for subsys in all_subsystems:
        if do_options:
            update_set.update(subsys.get_engine_options(aviary_options).keys())
        else:
            update_set.update(subsys.get_engine_inputs(aviary_options).keys())

    for var in update_set:
        if (var.startswith('aircraft:engine:') or var.startswith('aircraft.nacelle:')) and (meta_data[var]['option'] == do_options):
            dtype = meta_data[var]['types']
            default_value = meta_data[var]['default_value']
            multivalue = meta_data[var]['multivalue']
            units = meta_data[var]['units']

            # If dtype has multiple options, prefer type of default value
            # Otherwise, use the first type in the tuple
            if isinstance(dtype, tuple):
                if default_value is not None:
                    dtype = type(default_value)
                else:
                    dtype = dtype[0]

            if isiterable(meta_data[var]['types']):
                typeset = meta_data[var]['types']
            else:
                typeset = (meta_data[var]['types'],)

            # Variables are multidimensional if their base types have iterables, and are
            # flagged as `multivalue`
            multidimensional = set(typeset) & set((list, tuple, np.ndarray)) and multivalue

            # vec is where the vectorized engine data is stored - always a list right
            # now, converted to other types like np array later
            vec = []

            # Vectorize variable "var" from available sources #

            # If var is supposed to be a unique array per engine model, assemble flat
            # vector manually to avoid ragged arrays (such as for wing engine locations)

            # Priority order is (checked per engine):
            # 1. EngineModel.options
            # 2. non-engine model subsystems
            # 3. aviary_options
            # 4. default value from metadata

            # We already have the default value from the metadata.

            # Next, check if there's a value in `aviary_options`.
            try:
                val_aviary_options = np.atleast_1d(aviary_options.get_val(var, units))
            except (KeyError, IndexError):
                val_aviary_options = []

            # Now look for a value in each of the non-engine subsystems.
            vals_subsys = []
            subsys_with_var = []
            subsys_with_val = []
            szs_subsys = []
            for subsys in all_subsystems:
                if do_options:
                    subsys_options = subsys.get_engine_options(aviary_options)
                else:
                    subsys_options = subsys.get_engine_inputs(aviary_options)

                if var in subsys_options:
                    # This subsystem also uses this variable.
                    subsys_with_var.append(subsys)

                    # Get the size of this variable.
                    var_info_subsys = subsys_options[var]
                    sz_subsys = var_info_subsys.get("size", sz_default_subsys)

                    # The size declared by a non-engine subsystem should be length `num_engine_type`.
                    if not (len(sz_subsys) == num_engine_type):
                        raise ValueError(f"size declared for variable {var} by subsystem <{subsys.name}> should be a list of length {num_engine_type}, but has length {len(sz_subsys)}") # tested
                    if not multidimensional:
                        # A non-multidimensional variable means we expect a scalar variable per engine model, so the `sz_subsys` should be all ones or zeros.
                        if not all(((sz == 1) or (sz == 0)) for sz in sz_subsys):
                            raise ValueError(f"non-multidimensional variable {var} has at least one non-0 or non-1 size declared by subsystem <{subsys.name}>") # tested

                    # Save the size for checking later.
                    szs_subsys.append(sz_subsys)

                    # Does it have a value for the variable?
                    if "val" in var_info_subsys:
                        # Get value.
                        units_subsys = var_info_subsys.get("units", "unitless")
                        val = np.atleast_1d(var_info_subsys["val"])
                        if not (units_subsys == "unitless"):
                            val = convert_units(val, units_subsys, units)

                        # Check that `val` is the size we want.
                        sz_expected = np.sum(sz_subsys)
                        if val.size != sz_expected:
                            print(val, val.size, sz_expected)
                            raise ValueError(f"variable {var} in Model <{subsys.name}> does not have expected size {sz_expected}") # tested

                        # Save this value.
                        vals_subsys.append(val)
                        # Remember which models we found a value in.
                        subsys_with_val.append(subsys)

            if szs_subsys:
                # Check that the sizes found in all the subsystems match.
                if not all(sz == szs_subsys[0] for sz in szs_subsys):
                    subsys_names = [s.name for s in subsys_with_var]
                    raise ValueError(f"non-identical sizes for variable {var} found in multiple subsystems: {subsys_names}") # tested
                else:
                    sz_all_engines = szs_subsys[0]
            elif not multidimensional:
                # None of the non-engine subsystems declared a size for the variable.
                # So, for a non-multidimensional engine variable, default to a size of 1 for each engine model:
                sz_all_engines = sz_default_subsys
            else:
                sz_all_engines = []

            if vals_subsys:
                # Check if all the values found in the non-engine subsystems are the same.
                if not np.allclose(vals_subsys[0], vals_subsys):
                    subsys_names = [s.name for s in subsys_with_val]
                    raise ValueError(f"non-identical values for variable {var} found in multiple subsystems: {subsys_names}") # tested

                val_subsys = vals_subsys[0]
            else:
                # We didn't find a value for this variable in any of the non-engine subsystems.
                val_subsys = []

                # If we found a value in `aviary_options`, check that the size is what we expect.
                if (len(val_aviary_options) > 0) and sz_all_engines:
                    if multidimensional:
                        # If the current variable is multidimensional, then the value stored in `aviary_options` must be the correct size, i.e., values for all engines must be provided.
                        if not (val_aviary_options.size == np.sum(sz_all_engines)):
                            raise ValueError(f"size {val_aviary_options.size} of variable {var} found in aviary_options incompatible with sizes {sz_all_engines} found in non-engine subsystems") # tested
                    else:
                        # For non-multidimensional options, then we expect just one value per engine model.
                        num_val_aviary_options = len(val_aviary_options)
                        if num_val_aviary_options == 1:
                            # If we found just a single value in the `aviary_options`, repeat it to `num_engine_type`.
                            val_aviary_options = np.tile(val_aviary_options[0], num_engine_type)
                        elif num_val_aviary_options > 1:
                            # If we found more than one value, then we expect to have `num_engines_type` values.
                            if not (num_val_aviary_options == num_engine_type):
                                raise ValueError(f"incorrect number of values found for variable {var} in aviary_options: expected {num_engine_type} values (one per engine model), but found {num_val_aviary_options}") # tested

            # Do we know the size of this variable now?
            # * If any of the non-engine subsystems use this variable, then yes, because I've either checked what size the non-engine subsystem provided, or asummed it was scalar.
            # * If none of the non-engine subsystems use this variable, then:
            #   * if the variable is multidimensional, then I don't know the size.
            #   * if the variable **isn't** multidimensional, then I know, of course, that the size should just be `1` for each engine model.
            # So, a few unhandled cases:
            #   * If none of the non-engine subsystems use the variable **and** the variable is `multidimensional`, I don't know it's size.
            #     * Additionaly, if the above is true and there is a value in `aviary_options`, we would need to check that size, since I have no idea if that's correct.

            idx_var = 0
            sz_engine_models = []
            for idx_engine_model, engine in enumerate(engine_models):
                eng_name = engine.name
                # test to see if engine has this variable - if so, use it
                # try:
                #     # variables in engine models are trusted to be "safe", and only
                #     # contain data for that engine
                #     engine_val = engine.get_val(var, units)
                # # if the variable is not in the engine model, try the other subsystems:

                # First, check if the variable is an option needed by the current engine model.
                if do_options:
                    eng_options = engine.get_engine_options(aviary_options)
                else:
                    eng_options = engine.get_engine_inputs(aviary_options)
                if var in eng_options:
                    # This engine option is used by this engine model.
                    # Get the info associated with it:
                    var_info = eng_options[var]

                    # Get the expected size, defaulting to 1.
                    sz = var_info.get("size", 1)

                    # Check if the size matches what we found earlier from the non-engine subsystems (if we found any), or that it's 1 for non-multidimensional variables.
                    if sz_all_engines:
                        if not (sz == sz_all_engines[idx_engine_model]):
                            raise ValueError(f"declared size {sz} for variable {var} in EngineModel <{eng_name}> does not match expected size {sz_all_engines[idx_engine_model]}") # tested
                     
                    # Check if the value of the variable is known.
                    if "val" in var_info:
                        # Get the value, and confirm that the size is correct.
                        units_engine = var_info.get("units", "unitless")
                        val = np.atleast_1d(var_info["val"])
                        if type(var_info["val"]) in (int, float, np.int32, np.int64, np.float32, np.float64) and not (units == "unitless"):
                            val = convert_units(val, units_engine, units)
                        if val.size != sz:
                            raise ValueError(f"variable {var} in EngineModel <{eng_name}> does not have expected size {sz}, but has size {val.size}") # tested

                        # If the value we found in the engine model doesn't match what was in the non-engine subsystems, then raise a warning.
                        if (len(val_subsys) > 0) and (not np.allclose(val, val_subsys[idx_var:idx_var+sz])):
                            if verbosity >= Verbosity.BRIEF:
                                warnings.warn(
                                    f'value {val} for variable {var} in engine model <{eng_name}> is different from value {val_subsys[idx_var:idx_var+sz]} '
                                    'found in a non-engine subsystem. The engine model value will be used.'
                                )

                        if (len(val_aviary_options) > 0):
                            val_ao = val_aviary_options[idx_var:idx_var+sz]
                            if not (val_ao.size == sz):
                                raise ValueError(f"value for variable {var} taken from aviary_options argument has too-small size") # tested
                            if not np.allclose(val, val_ao):
                                if verbosity >= Verbosity.BRIEF:
                                    warnings.warn(
                                        f'value {val} for variable {var} in engine model <{eng_name}> is different from value {val_ao} '
                                        'found in the aviary_options argument. The engine model value will be used.'
                                    )

                    elif len(val_subsys) > 0:
                        # We know the engine model needs variable `var`, but it isn't present in the engine model.
                        # We also know the size.
                        # So, we can take it from the values found in the non-engine subsystems.
                        val = val_subsys[idx_var:idx_var+sz]
                        # Do we need to check the length of that?
                        # We've checked that `val_subsys`'s size matches the size declared in the non-engine subsystems, and we've checked that the size declared in the engine model for this variable matches the size declared in the non-engine subsystem.
                        # So then I think part of the `val_subsys` that we're slicing will also be good.

                        # But if we found a value in the aviary_options argument that's different, warn the user about that.
                        if (len(val_aviary_options) > 0):
                            val_ao = val_aviary_options[idx_var:idx_var+sz]
                            if not (val_ao.size == sz):
                                if verbosity >= Verbosity.BRIEF:
                                    warnings.warn(
                                        f'value {val_ao} for variable {var} intended for engine model <{eng_name}> is too small, '
                                        f'but an appropriately-sized value {val} was found in a non-engine subsystem and will be used.'
                                    )
                            if not np.allclose(val, val_ao):
                                if verbosity >= Verbosity.BRIEF:
                                    warnings.warn(
                                        f'value {val} for variable {var} taken from a non-engine subsystem for engine model <{eng_name}> is different from value {val_ao} '
                                        'found in the aviary_options argument. The non-engine subsystem value will be used.'
                                    )

                        # Add the value to the engine model's `options` attribute.
                        if multidimensional:
                            engine.set_val(var, val, units)
                        else:
                            engine.set_val(var, val[0], units)

                    elif len(val_aviary_options) > 0:
                        # We don't have a value from either the engine model or the non-engine subsystems for this variable, but we did find something in `aviary_options`.
                        # Get the value for this engine model from that, and check that we have enough values.
                        val = val_aviary_options[idx_var:idx_var+sz]
                        if not (val.size == sz):
                            raise ValueError(f"value for variable {var} taken from aviary_options argument has too-small size") # tested

                        # Add the value to the engine model's `options` attribute.
                        if multidimensional:
                            engine.set_val(var, val, units)
                        else:
                            engine.set_val(var, val[0], units)
                    else:
                        # Only place left to get a value is from the default value in the metadata.
                        val = np.tile(default_value, sz)

                        # Add the value to the engine model's `options` attribute.
                        if multidimensional:
                            engine.set_val(var, val, units)
                        else:
                            engine.set_val(var, val[0], units)

                    # Add a flattened version of the value to `vec`.
                    # This will work for `ndarray`s with `ndim > 1`, but I don't think Aviary as a whole actually supports that sort of thing.
                    vec.extend(val.flat)

                    # Increment the index keeping track of the variable.
                    idx_var += sz

                else:
                    # `var` is not an option needed by this engine model.
                    sz = 0

                    # What do we do about the vec?
                    # Do we know it's size?
                    # We would if it's used by any non-engine subsystem.
                    # And it has to be, right?
                    # Well, not necessarily.
                    # It could be used by one engine model and not another *and* not by any of the non-engine subsystems.
                    # So, anyway, first check if we have a value from the non-engine subsystems:
                    if sz_all_engines:
                        sz_subsys_this_engine = sz_all_engines[idx_engine_model]

                        if len(val_subsys) > 0:
                            val = val_subsys[idx_var:idx_var+sz_subsys_this_engine]
                        elif len(val_aviary_options) > 0:
                            val = val_aviary_options[idx_var:idx_var+sz_subsys_this_engine]
                            # I don't think there's any reason to test for this, since we've already confirmed that `val_aviary_options` has the expected size.
                            if not (val.size == sz_subsys_this_engine):
                                raise ValueError(f"value for variable {var} taken from aviary_options argument has too-small size")
                        else:
                            # Only place left to get a value is from the default value in the metadata.
                            val = np.tile(default_value, sz_subsys_this_engine)

                        # Add a flattened version of the value to `vec`.
                        # This will work for `ndarray`s with `ndim > 1`, but I don't think Aviary as a whole actually supports that sort of thing.
                        vec.extend(val.flat)

                        # Increment the index keeping track of the variable.
                        idx_var += sz_subsys_this_engine

                    else:
                        # This means that none of the non-engine subsystems use this variable **and** the variable is multidimensional.
                        # So, what do we do about the value?
                        # Well, we don't really need a value, right?
                        # Right, the size will be zero, so, yeah.
                        pass


                # Save the size for this engine model for checking later.
                sz_engine_models.append(sz)

            if sz_all_engines:
                # Check that the size we found with the non-engine subsystems (or non-multidimensional variable) matches what the engine models declared.
                # But if the size in `sz_engine` is 0, that means that the engine doesn't use the variable, and we don't need to check that the size matches what was found in the non-engine subsystems.
                # But I think we've already checked this individually for each engine model.
                if not all((sz_engine == 0) or (sz_engine == sz_subsys) for sz_engine, sz_subsys in zip(sz_engine_models, sz_all_engines)):
                    raise ValueError(f"size for variable {var} declared by engine models does not match that declared by non-engine subsystems and/or its multidimensional-ness")
            else:
                # We never got any size information earlier, so use what we found in the engine models.
                sz_all_engines = sz_engine_models

            # Update aviary options with new vectors
            # If data is numerical, store in a numpy array, else use a list
            # Some machines default to specific-bit np array types, so we have to
            # check for those too
            if type(vec[0]) in (int, float, np.int32, np.int64, np.float32, np.float64):
                vec = np.array(vec, dtype=dtype)
            aviary_options.set_val(var, vec, units)

def preprocess_propulsion(
    aviary_options: AviaryValues,
    all_subsystems: list,
    engine_models: list = None,
    meta_data=_MetaData,
    verbosity=None,
):
    """
    Updates AviaryValues object with values taken from provided EngineModels.

    Vectorizes variables in aviary_options in the correct order for vehicles with
    heterogeneous engines.

    Performs basic sanity checks on inputs that are universal to all EngineModels.

    !!! WARNING !!!
    Values in aviary_options can be overwritten with corresponding values from
    engine_models!

    Parameters
    ----------
    aviary_options : AviaryValues
        Options to be updated. EngineModels (provided or generated) are added, and
        Aircraft:Engine:* and Aircraft:Nacelle:* variables are vectorized as numpy arrays

    all_subsystems : <list of subsystems>
        Subsystems used to determine engine-related variables needed

    engine_models : <list of EngineModels> (optional)
        EngineModel objects to be added to aviary_options. Replaced existing EngineModels
        in aviary_options
    """
    if verbosity is not None:
        # compatibility with being passed int for verbosity
        verbosity = Verbosity(verbosity)
    else:
        if verbosity in aviary_options:
            verbosity = aviary_options.get_val(Settings.VERBOSITY)
        else:
            verbosity = Verbosity.BRIEF

    ##############################
    # Vectorize Engine Variables #
    ##############################
    # Only vectorize variables user has defined in some way or engine model has calculated
    # Combine aviary_options and all engine options into single AviaryValues
    # It is assumed that all EngineModels are up-to-date at this point and will NOT
    # be changed later on (otherwise preprocess_propulsion must be run again)
    num_engine_type = len(engine_models)

    # # update_list has keys of all variables that are already defined, and must
    # # be vectorized
    # update_list = list(get_keys(complete_options_list))

    # # Vectorize engine variables. Only update variables in update_list that are relevant
    # # to engines (defined by _get_engine_variables())
    # for var in _get_engine_variables():
    #     if var in update_list:
    #         dtype = meta_data[var]['types']
    #         default_value = meta_data[var]['default_value']
    #         multivalue = meta_data[var]['multivalue']
    #         units = meta_data[var]['units']

    #         # If dtype has multiple options, prefer type of default value
    #         # Otherwise, use the first type in the tuple
    #         if isinstance(dtype, tuple):
    #             if default_value is not None:
    #                 dtype = type(default_value)
    #             else:
    #                 dtype = dtype[0]

    #         if isiterable(meta_data[var]['types']):
    #             typeset = meta_data[var]['types']
    #         else:
    #             typeset = (meta_data[var]['types'],)

    #         # Variables are multidimensional if their base types have iterables, and are
    #         # flagged as `multivalue`
    #         multidimensional = set(typeset) & set((list, tuple, np.ndarray)) and multivalue

    #         # vec is where the vectorized engine data is stored - always a list right
    #         # now, converted to other types like np array later
    #         vec = []

    #         # Vectorize variable "var" from available sources #

    #         # If var is supposed to be a unique array per engine model, assemble flat
    #         # vector manually to avoid ragged arrays (such as for wing engine locations)

    #         # Priority order is (checked per engine):
    #         # 1. EngineModel.options
    #         # 2. aviary_options
    #         # 3. default value from metadata
    #         for i, engine in enumerate(engine_models):
    #             eng_name = engine.name
    #             # test to see if engine has this variable - if so, use it
    #             try:
    #                 # variables in engine models are trusted to be "safe", and only
    #                 # contain data for that engine
    #                 engine_val = engine.get_val(var, units)
    #             # if the variable is not in the engine model, pull from aviary options
    #             except KeyError:
    #                 # check if variable is defined in aviary options (for this engine's
    #                 # index) - if so, use it
    #                 try:
    #                     aviary_val = aviary_options.get_val(var, units)
    #                 # if the variable is not in aviary_options, use default from metadata
    #                 except (KeyError, IndexError):
    #                     vec.append(default_value)
    #                 else:
    #                     # save value from aviary_options
    #                     if isiterable(aviary_val):
    #                         if multidimensional:
    #                             vec.extend(aviary_val)
    #                         else:
    #                             # if aviary_val is an iterable, just grab val for this engine
    #                             vec.append(aviary_val[i])
    #                     else:
    #                         vec.append(aviary_val)
    #             else:
    #                 # save value from EngineModel
    #                 # if isiterable(engine_val) and multidimensional:
    #                 #     vec.extend(engine_val)
    #                 # else:
    #                 #     vec.append(engine_val)
    #                 if isiterable(engine_val):
    #                     if multidimensional:
    #                         vec.extend(engine_val)
    #                     else:
    #                         # `engine_val` is iterable, but we didn't expect it to be according to the metadata.
    #                         # So just take the first value.
    #                         if len(engine_val) > 1:
    #                             warnings.warn(
    #                                 f'variable {var} found in engine model <{eng_name}> is iterable, '
    #                                 'but a scalar value was expected. Taking the first value only.'
    #                             )
    #                         vec.append(engine_val[0])
    #                 else:
    #                     if multidimensional:
    #                         # `engine_val` is not iterable, but we expected it to be according to the metadata.
    #                         # So we'll just append it to `vec`, which is equivalent to treating it as a length-1 iterable.
    #                         warnings.warn(
    #                             f'variable {var} found in engine model <{eng_name}> is scalar, '
    #                             'but an iterable value was expected. Using the (single) value anyway.'
    #                         )
    #                     vec.append(engine_val)
    #             # TODO update each engine's options with "new" values? Allows each engine
    #             #      to have a copy of all options/inputs, beyond what it was
    #             #      originally initialized with

    #         # Update aviary options with new vectors
    #         # If data is numerical, store in a numpy array, else use a list
    #         # Some machines default to specific-bit np array types, so we have to
    #         # check for those too
    #         if type(vec[0]) in (int, float, np.int32, np.int64, np.float32, np.float64):
    #             vec = np.array(vec, dtype=dtype)
    #         aviary_options.set_val(var, vec, units)

    _reconcile_engine_vars(aviary_options, all_subsystems, engine_models, meta_data, do_options=True, verbosity=verbosity)

    ###################################
    # Input/Option Consistency Checks #
    ###################################
    # Make sure number of engines based on mount location match expected total
    try:
        num_engines_all = aviary_options.get_val(Aircraft.Engine.NUM_ENGINES)
    except KeyError:
        num_engines_all = np.zeros(num_engine_type).astype(int)
    try:
        num_fuse_engines_all = aviary_options.get_val(Aircraft.Engine.NUM_FUSELAGE_ENGINES)
    except KeyError:
        num_fuse_engines_all = np.zeros(num_engine_type).astype(int)
    try:
        num_wing_engines_all = aviary_options.get_val(Aircraft.Engine.NUM_WING_ENGINES)
    except KeyError:
        num_wing_engines_all = np.zeros(num_engine_type).astype(int)

    for i, engine in enumerate(engine_models):
        eng_name = engine.name
        num_engines = num_engines_all[i]
        num_fuse_engines = num_fuse_engines_all[i]
        num_wing_engines = num_wing_engines_all[i]
        total_engines_calc = num_fuse_engines + num_wing_engines

        # If engine mount type is not specified at all, default to wing (unless there is
        # only one engine, in which case default to fuselage)
        if total_engines_calc == 0:
            if num_engines > 1:
                num_wing_engines_all[i] = num_engines
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                    warnings.warn(
                        f'Mount location for engines of type <{eng_name}> not '
                        'specified. Wing-mounted engines are assumed.'
                    )
            else:
                num_fuse_engines_all[i] = num_engines
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                    warnings.warn(
                        f'Mount location for single engine of type <{eng_name}> not '
                        'specified. Assuming it is fuselage-mounted.'
                    )

        # If wing mount type are specified but inconsistent, handle it
        elif total_engines_calc > num_engines:
            # more defined engine locations than number of engines - increase num engines
            num_engines_all[i] = total_engines_calc
            if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                warnings.warn(
                    'Sum of user-specified fuselage-mounted and wing-mounted engines do '
                    f'not match total number of engines for EngineModel <{eng_name}>. '
                    'Overwriting total number of engines with the sum of wing and '
                    'fuselage mounted engines.'
                )
        elif total_engines_calc < num_engines:
            # fewer defined locations than num_engines - assume rest are wing mounted
            # (unless there is just one prospective wing engine, then fuselage mount it)
            num_unspecified_engines = num_engines - num_fuse_engines - num_wing_engines
            if num_unspecified_engines > 1:
                num_wing_engines_all[i] = num_wing_engines + num_unspecified_engines
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                    warnings.warn(
                        'Mount location was not defined for all engines of EngineModel '
                        f'<{eng_name}> - unspecified engines are assumed wing-mounted.'
                    )
            elif num_unspecified_engines == 1 and num_wing_engines != 0:
                num_fuse_engines_all[i] = num_fuse_engines + num_unspecified_engines
                if verbosity >= Verbosity.BRIEF:  # BRIEF, VERBOSE, DEBUG
                    warnings.warn(
                        'Mount location was not defined for all engine of EngineModel '
                        f'<{eng_name}> - unspecified engine is assumed fuselage-mounted.'
                    )

        if num_wing_engines % 2 == 1:
            if verbosity >= Verbosity.VERBOSE:  # VERBOSE, DEBUG
                warnings.warn(
                    'Odd number of wing engines are specified for EngineModel '
                    f'<{eng_name}> - this may cause issues with some mass and geometry '
                    'components that assume symmetric wing engine distribution.'
                )

    aviary_options.set_val(Aircraft.Engine.NUM_ENGINES, num_engines_all)
    aviary_options.set_val(Aircraft.Engine.NUM_WING_ENGINES, num_wing_engines_all)
    aviary_options.set_val(Aircraft.Engine.NUM_FUSELAGE_ENGINES, num_fuse_engines_all)

    if Mission.Summary.FUEL_FLOW_SCALER not in aviary_options:
        aviary_options.set_val(Mission.Summary.FUEL_FLOW_SCALER, 1.0)

    num_engines = aviary_options.get_val(Aircraft.Engine.NUM_ENGINES)
    total_num_engines = int(sum(num_engines_all))
    total_num_fuse_engines = int(sum(num_fuse_engines_all))
    total_num_wing_engines = int(sum(num_wing_engines_all))

    # compute propulsion-level engine count totals here
    aviary_options.set_val(Aircraft.Propulsion.TOTAL_NUM_ENGINES, total_num_engines)
    aviary_options.set_val(Aircraft.Propulsion.TOTAL_NUM_FUSELAGE_ENGINES, total_num_fuse_engines)
    aviary_options.set_val(Aircraft.Propulsion.TOTAL_NUM_WING_ENGINES, total_num_wing_engines)

    # Now that we have the correct options, do the engine inputs, too.
    _reconcile_engine_vars(aviary_options, all_subsystems, engine_models, meta_data, do_options=False, verbosity=verbosity)

def _get_engine_variables():
    """Yields all propulsion-related variables in Aircraft that need to be vectorized."""
    for item in get_names_from_hierarchy(Aircraft.Engine):
        yield item

    for item in get_names_from_hierarchy(Aircraft.Nacelle):
        yield item
