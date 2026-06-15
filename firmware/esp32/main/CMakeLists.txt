idf_component_register(SRCS "main.c"
                       INCLUDE_DIRS "."
                       REQUIRES sensors lora storage config ota payload)
