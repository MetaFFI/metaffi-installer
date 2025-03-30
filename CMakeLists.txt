## Define paths
##set(CONTAINERS_DIR "${CMAKE_SOURCE_DIR}/containers")
##set(METAFFI_INSTALLER_DONE "${CMAKE_BINARY_DIR}/metaffi_installer_done")
##set(MOVE_INSTALLERS_DONE "${CMAKE_BINARY_DIR}/move_installers_done")
#
## if in Windows, and METAFFI_WIN_HOME is not set, set it to the METAFFI_HOME
#if(NOT DEFINED ENV{METAFFI_WIN_HOME} OR NOT DEFINED ENV{METAFFI_UBUNTU_HOME})
#	message(FATAL_ERROR "METAFFI_WIN_HOME and METAFFI_UBUNTU_HOME must be set")
#endif()
#
## Define plugin paths and names using | as separator
#set(PLUGIN_INSTALLERS
#		"${CMAKE_SOURCE_DIR}/lang-plugin-python311|python311"
#		"${CMAKE_SOURCE_DIR}/lang-plugin-openjdk|openjdk"
#		"${CMAKE_SOURCE_DIR}/lang-plugin-go|go"
#)
#
## --- Build MetaFFI Installer ---
#add_custom_command(
#		OUTPUT ${METAFFI_INSTALLER_DONE}
#		COMMAND ${PYTHON_EXECUTABLE} build_metaffi_installer.py
#		COMMAND ${CMAKE_COMMAND} -E touch ${METAFFI_INSTALLER_DONE}
#		WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
#		COMMENT "Building MetaFFI installer..."
#)
#
## Collect plugin installer output dependencies
#set(PLUGIN_COMMANDS)
#foreach(PLUGIN_ENTRY ${PLUGIN_INSTALLERS})
#	# Split entry using "|" instead of ";"
#	string(REPLACE "|" ";" PLUGIN_LIST ${PLUGIN_ENTRY})
#	list(LENGTH PLUGIN_LIST LEN)
#
#	if (LEN EQUAL 2)
#		list(GET PLUGIN_LIST 0 PLUGIN_PATH)
#		list(GET PLUGIN_LIST 1 PLUGIN_NAME)
#
#		set(PLUGIN_DONE_FILE "${CMAKE_BINARY_DIR}/plugin_${PLUGIN_NAME}_done")
#
#		add_custom_command(
#				OUTPUT ${PLUGIN_DONE_FILE}
#				COMMAND ${CMAKE_COMMAND} -E env
#				"PLUGIN_INSTALLER_DEV_PATH=${PLUGIN_PATH}"
#				"PLUGIN_INSTALLER_PLUGIN_NAME=${PLUGIN_NAME}"
#				${Python3_EXECUTABLE} build_plugin_installer.py
#				COMMAND ${CMAKE_COMMAND} -E touch ${PLUGIN_DONE_FILE}
#				WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
#				COMMENT "Building ${PLUGIN_NAME} plugin installer..."
#				DEPENDS ${METAFFI_INSTALLER_DONE}
#		)
#
#		list(APPEND PLUGIN_COMMANDS ${PLUGIN_DONE_FILE})
#	else()
#		message(FATAL_ERROR "Invalid plugin entry: ${PLUGIN_ENTRY}")
#	endif()
#endforeach()
#
## --- Move Installers to Containers ---
##
##add_custom_command(
##		OUTPUT ${MOVE_INSTALLERS_DONE}
##		COMMAND ${CMAKE_COMMAND} -E make_directory ${CONTAINERS_DIR}
##		COMMAND ${CMAKE_COMMAND} -E rename ${CMAKE_SOURCE_DIR}/metaffi-installer/metaffi_installer.py ${CONTAINERS_DIR}/metaffi_installer.py
##		COMMAND ${CMAKE_COMMAND} -E rename ${CMAKE_SOURCE_DIR}/metaffi-installer/metaffi_plugin_python311_installer.py ${CONTAINERS_DIR}/metaffi_plugin_python311_installer.py
##		COMMAND ${CMAKE_COMMAND} -E rename ${CMAKE_SOURCE_DIR}/metaffi-installer/metaffi_plugin_python312_installer.py ${CONTAINERS_DIR}/metaffi_plugin_python312_installer.py
##		COMMAND ${CMAKE_COMMAND} -E rename ${CMAKE_SOURCE_DIR}/metaffi-installer/metaffi_plugin_openjdk_installer.py ${CONTAINERS_DIR}/metaffi_plugin_openjdk_installer.py
##		COMMAND ${CMAKE_COMMAND} -E rename ${CMAKE_SOURCE_DIR}/metaffi-installer/metaffi_plugin_go_installer.py ${CONTAINERS_DIR}/metaffi_plugin_go_installer.py
##		COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_SOURCE_DIR}/metaffi-installer/requirements.txt ${CONTAINERS_DIR}/requirements.txt
##		COMMAND ${CMAKE_COMMAND} -E touch ${MOVE_INSTALLERS_DONE}
##		COMMENT "Moving installers to containers directory..."
##		DEPENDS ${PLUGIN_COMMANDS}
##)
##
## --- Define Final Target (Not Built by Default) ---
#add_custom_target(build_metaffi_installers
#	COMMENT "Building all MetaFFI installers..."
#)
