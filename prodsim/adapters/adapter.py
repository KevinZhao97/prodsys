from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Set
from pydantic import parse_obj_as, BaseModel, validator

from prodsim.data_structures import (
    queue_data,
    resource_data,
    time_model_data,
    state_data,
    processes_data,
    material_data,
    sink_data,
    source_data,
)


def load_json(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    return data

def get_set_of_IDs(list_of_objects: List[Any]) -> Set[str]:
    return set([obj.ID for obj in list_of_objects])


class Adapter(ABC, BaseModel):

    valid_configuration: bool = True
    reconfiguration_cost: float = 0

    time_model_data: List[time_model_data.TIME_MODEL_DATA] = []
    state_data: List[state_data.STATE_DATA_UNION] = []
    process_data: List[processes_data.PROCESS_DATA_UNION] = []
    queue_data: List[queue_data.QueueData] = []
    resource_data: List[resource_data.RESOURCE_DATA_UNION] = []
    material_data: List[material_data.MaterialData] = []
    sink_data: List[sink_data.SinkData] = []
    source_data: List[source_data.SourceData] = []
    seed: int = 21
    
    class Config:
        validate_assignment = True
    


    @validator("state_data", each_item=True)
    def check_states(cls, state, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if state.time_model_id not in time_models:
            raise ValueError(
                    f"The time model {state.time_model_id} of state {state.ID} is not a valid time model of {time_models}."
                )
        return state
    
    @validator("process_data", each_item=True)
    def check_processes(cls, process, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if process.time_model_id not in time_models:
            raise ValueError(
                    f"The time model {process.time_model_id} of process {process.ID} is not a valid time model of {time_models}."
                )
        return process
    
    @validator("resource_data", each_item=True)
    def check_resources(cls, resource, values):
        processes = get_set_of_IDs(values["process_data"])
        for process in resource.processes:
            if process not in processes:
                raise ValueError(
                    f"The process {process} of resource {resource.ID} is not a valid process of {processes}."
                )
        states = get_set_of_IDs(values["state_data"])
        for state in resource.states:
            if state not in states:
                raise ValueError(
                    f"The state {state} of resource {resource.ID} is not a valid state of {states}."
                )
        if isinstance(resource, resource_data.ProductionResourceData):
            queues = get_set_of_IDs(values["queue_data"])
            for queue in resource.input_queues + resource.output_queues:
                if queue not in queues:
                    raise ValueError(
                        f"The queue {queue} of resource {resource.ID} is not a valid queue of {queues}."
                    )
                
        return resource

    @validator("material_data", each_item=True)
    def check_materials(cls, material, values):
        processes = get_set_of_IDs(values["process_data"])
        if not material.transport_process in processes:
            raise ValueError(
                f"The transport process {material.transport_process} of material {material.ID} is not a valid process of {processes}."
            )
        if isinstance(material.processes, list):
            for process in material.processes:
                if process not in processes:
                    raise ValueError(
                        f"The process {process} of material {material.ID} is not a valid process of {processes}."
                    )
        return material

    @validator("sink_data", each_item=True)
    def check_sinks(cls, sink, values):
        materials = get_set_of_IDs(values["material_data"])
        if sink.material_type not in materials:
            raise ValueError(
                f"The material type {sink.material_type} of sink {sink.ID} is not a valid material of {materials}."
            )
        queues = get_set_of_IDs(values["queue_data"])
        for q in sink.input_queues:
            if q not in queues:
                raise ValueError(
                    f"The queue {q} of sink {sink.ID} is not a valid queue of {queues}."
                )
        return sink
    
    @validator("source_data", each_item=True)
    def check_sources(cls, source, values):
        time_models = get_set_of_IDs(values["time_model_data"])
        if source.time_model_id not in time_models:
            raise ValueError(
                    f"The time model {source.time_model_id} of source {source.ID} is not a valid time model of {time_models}."
                )
        materials = get_set_of_IDs(values["material_data"])
        if source.material_type not in materials:
            raise ValueError(
                f"The material type {source.material_type} of source {source.ID} is not a valid material of {materials}."
            )
        queues = get_set_of_IDs(values["queue_data"])
        for q in source.output_queues:
            if q not in queues:
                raise ValueError(
                    f"The queue {q} of source {source.ID} is not a valid queue of {queues}."
                )
        return source

    @abstractmethod
    def read_data(self, file_path: str):
        pass

    @abstractmethod
    def write_data(self, file_path: str):
        pass


class JsonAdapter(Adapter):
    def read_data(self, file_path: str):
        data = load_json(file_path=file_path)
        self.seed = data["seed"]
        self.time_model_data = self.create_objects_from_configuration_data(
            data["time_models"], time_model_data.TIME_MODEL_DATA
        )
        self.state_data = self.create_objects_from_configuration_data(
            data["states"], state_data.STATE_DATA_UNION
        )
        self.process_data = self.create_objects_from_configuration_data(
            data["processes"], processes_data.PROCESS_DATA_UNION
        )

        self.queue_data = self.create_objects_from_configuration_data(data["queues"], queue_data.QueueData)
        self.resource_data = self.create_objects_from_configuration_data(data["resources"], resource_data.RESOURCE_DATA_UNION)
        self.material_data = self.create_objects_from_configuration_data(data["materials"], material_data.MaterialData)
        self.sink_data = self.create_objects_from_configuration_data(data["sinks"], sink_data.SinkData)
        self.source_data = self.create_objects_from_configuration_data(data["sources"], source_data.SourceData)

    def create_typed_object_from_configuration_data(
        self, configuration_data: Dict[str, Any], type
    ):
        objects = []
        for cls_name, items in configuration_data.items():
            for values in items.values():
                values.update({"type": cls_name})
                objects.append(parse_obj_as(type, values))
        return objects
    
    def create_objects_from_configuration_data(
        self, configuration_data: Dict[str, Any], type
    ):  
        objects = []
        for values in configuration_data.values():
            objects.append(parse_obj_as(type, values))
        return objects

    def write_data(self, file_path: str):
        data = self.get_dict_object_of_adapter()
        with open(file_path, "w") as json_file:
            json.dump(data, json_file)

    def get_dict_object_of_adapter(self) -> dict:
        data = {
                "seed": self.seed,
                "time_models": self.get_dict_of_list_objects(self.time_model_data),
                "states": self.get_dict_of_list_objects(self.state_data),
                "processes": self.get_dict_of_list_objects(self.process_data),
                "queues": self.get_dict_of_list_objects(self.queue_data),
                "resources": self.get_dict_of_list_objects(self.resource_data),
                "materials": self.get_dict_of_list_objects(self.material_data),
                "sinks": self.get_dict_of_list_objects(self.sink_data),
                "sources": self.get_dict_of_list_objects(self.source_data)
        }
        return data

    def get_dict_of_list_objects(self, values: List[BaseModel]) -> dict:
        return {counter: data.dict() for counter, data in enumerate(values)}