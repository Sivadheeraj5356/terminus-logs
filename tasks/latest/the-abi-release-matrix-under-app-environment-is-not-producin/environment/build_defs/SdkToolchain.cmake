function(sdk_register_idl_inputs out_var)
  set(_idl
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/provenance.manifest"
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/compat/legacy_slots.tsv"
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/fragments/00_core.sdk"
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/fragments/10_runtime.sdk"
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/fragments/15_lifecycle.sdk"
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/fragments/18_observability.sdk"
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/fragments/20_diagnostics.sdk"
    "${CMAKE_CURRENT_SOURCE_DIR}/idl/fragments/30_recovery.sdk"
  )
  set(${out_var} "${_idl}" PARENT_SCOPE)
endfunction()

function(sdk_add_generator)
  add_executable(genabi
    tools/genabi/main.cpp
    tools/genabi/parse.cpp
    tools/genabi/layout.cpp
    tools/genabi/render.cpp
    tools/genabi/digest.cpp
  )
  target_include_directories(genabi PRIVATE tools/genabi)
  sdk_apply_warnings(genabi)
endfunction()

function(sdk_add_shape)
  set(GEN_INCLUDE_ROOT "${CMAKE_BINARY_DIR}/generated/include")
  set(GEN_HEADER "${GEN_INCLUDE_ROOT}/generated/sdk.hpp")
  set(GEN_LAYOUT "${CMAKE_BINARY_DIR}/generated/sdk.layout.json")

  sdk_register_idl_inputs(SDK_IDL_INPUTS)

  add_custom_command(
    OUTPUT "${GEN_HEADER}"
    BYPRODUCTS "${GEN_LAYOUT}"
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${GEN_INCLUDE_ROOT}/generated"
    COMMAND genabi
            --idl-dir "${CMAKE_CURRENT_SOURCE_DIR}/idl"
            --lane-file "${SDK_LANE_FILE}"
            --label "${SDK_LANE_LABEL}"
            --out-header "${GEN_HEADER}"
            --out-layout "${GEN_LAYOUT}"
    DEPENDS genabi "${SDK_LANE_FILE}" ${SDK_IDL_INPUTS}
    COMMENT "Generating SDK ABI shape for ${SDK_LANE_LABEL}"
    VERBATIM
  )

  add_custom_target(sdk_generate DEPENDS "${GEN_HEADER}")

  add_executable(sdk_probe src/probe.cpp "${GEN_HEADER}")
  add_dependencies(sdk_probe sdk_generate)
  target_include_directories(sdk_probe PRIVATE
    "${GEN_INCLUDE_ROOT}"
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
  )
  sdk_apply_warnings(sdk_probe)
endfunction()
