import numpy as np
import zipfile
import logging
from typing import *
from allensdk.api.queries.ontologies_api import OntologiesApi
import matplotlib.pyplot as plt
from colormap import Color
try:
    from ipywidgets import interact, interactive, fixed, interact_manual
    import ipywidgets as widgets
except ImportError:
    logging.warn("ipywidgets is not installed some function will not be available")


class AllenBrainStructure:
    def __init__(self, object_dict: Dict[str, Any], atlas: Any) -> None:
        for k, v in object_dict.items():
            setattr(self, k, v)
        self.children = []  # type: List
        self.parent = None  # type: Any
        self._atlas = atlas
        
    def add_children(self, other: Any) -> None:
        if other not in self.children:
            self.children.append(other)
            other.set_parent(self)
            
    def set_parent(self, other) -> None:
        if self.parent is None:
            self.parent = other
            other.add_children(self)
            
    def connect(self) -> None:
        if self.parent_structure_id is not None:
            parent_obj = self._atlas[self.parent_structure_id]
            self.set_parent(parent_obj)
        else:
            pass
    
    def __repr__(self) -> str:
        head = super(AllenBrainStructure, self).__repr__()
        memory_address = head.split(" ")[-1][:-1]
        return '<AllenBrainStructure %s "%s" at %s>' % (self.id, self.safe_name, memory_address)
    
    def _repr_html_(self) -> str:
        html = "<p>"
        html += "<table>"
        html += '<tr align="center">'
        html += "<td>&nbsp;</td>"
        html += "<td><strong>%s</strong></td>" % self.safe_name
        html += "</tr>"
        entries_to_print = ["acronym", "name", "id", "graph_order",
                            "st_level", "depth", "structure_id_path"]
        for k in entries_to_print:
            v = getattr(self, k)
            html += '<tr align="center">'
            html += "<td><strong>" + str(k) + "</strong></td>"
            html += "<td>" + str(v) + "</td>"
            html += "</tr>"
        html += '<tr><td><strong>color</strong></td>'
        html += '<td bgcolor="#%s">%s</td></tr>' % (self.color_hex_triplet, self.color_hex_triplet)
        html += "</table>"
        return html


class AllenBrainReference:
    def __init__(self, graph="adult"):
        self._onto = OntologiesApi()
        if graph == "adult":
            self._struct_dicts_list = self._onto.get_structures(structure_graph_ids=1, num_rows='all')
        elif graph == "development":
            self._struct_dicts_list = self._onto.get_structures(structure_graph_ids=17, num_rows='all')
        self._structures = {i["id"]: AllenBrainStructure(i, self) for i in self._struct_dicts_list}
        self._link()
    
    def __getitem__(self, key: int) -> Any:
        return self._structures[key]
    
    def __iter__(self) -> Any:
        for k, v in self._structures.items():
            yield v
    
    def _link(self) -> None:
        for name, structure in self._structures.items():
            structure.connect()


class Reference3D:
    def __init__(self):
        pass
                
    
class AllenVolumetricData:
    def __init__(self, filename: str, reference: Any=None) -> None:
        self.filename = filename
        self.zip_container = zipfile.ZipFile(filename)
        for i in zip_container.infolist():
            if ".mhd" in i.filename:
                mhd_file = i
            if '.raw' in i.filename:
                raw_file = i
        info_file = self.zip_container.open(mhd_file).read().decode("ascii")
        entries_file = [i.split(" = ") for i in info_file.rstrip().split("\n")]
        self.file_info = {k:([int(i) for i in v.split(" ")] if (" " in v) else (k,v)) for k, v in entries_file }
        self.shape = tuple(self.file_info['DimSize'])
        self.is_label = ("UINT" in self.file_info['ElementType'][1])
        self.file_type = 'uint32' if self.is_label else 'uint8'
        logging.debug("Reading data file")
        buffer = zip_container.open(raw_file).read()
        array1d = np.fromstring(buffer, dtype=file_type)
        if self.is_label:
            self.ids, array1d = np.unique(array1d, return_inverse=True)
        self._values = array1d.reshape(dim_size, order='F')
        self.zip_container.close()
        self.reference = reference
        if self.is_label:
            self._colored = ColoredVolumetric(self)
        
    def __getitem__(self, slice_obj):
        return self._values[slice_obj]
    
    @property
    def reference(self):
        try:
            return self._reference
        except NameError:
            self._reference = None
            return self.reference
    
    @reference.setter
    def reference(self, reference_object: Any) -> None:
        self._reference = reference_object
        self.color_table = np.zeros((len(self.ids), 3))
        for i, idx in enumerate(self.ids):
            try:
                self.color_table[i, :] = Color("#" + self._reference[idx].color_hex_triplet).rgb
            except KeyError:
                self.color_table[i, :] = Color("#000000").rgb

    @property    
    def colored(self):
        return self._colored
    
    def plot_slides(self, coronal, sagittal, ss=None, fig=None, return_figure=False):
        if self.is_label and self.reference:
            self.colored.plot_slides(coronal=coronal, sagittal=sagittal, ss=ss, fig=fig, return_figure=return_figure)
        else:
            if fig is None:
                fig = plt.gcf()
            if ss is None:
                ss = plt.GridSpec(1,1)[0]
            if return_figure:
                fig.clear()
            gs = GridSpecFromSubplotSpec(1, 2, subplot_spec=ss)
            ax = fig.add_subplot(gs[0])
            ax.imshow(self[coronal, :, :], cmap="gray" )
            ax.axvline(sagittal, c='y', lw=1)
            ax = fig.add_subplot(gs[1])
            ax.imshow(self[:,:,sagittal].T, cmap="gray" )
            ax.axvline(coronal, c='y', lw=1)
            if return_figure:
                return fig
        
    def interactive_slides(self):
        fig = plt.figure(figsize=(12,5))
        gs = plt.GridSpec(1,1)
        interact(self.plot_slides, coronal=(0, self.shape[0]-1),
                 sagittal=(0, self.shape[-1]-1), ss=fixed(gs[0]), fig=fixed(fig))
        plt.clf()
        

class ColoredVolumetric:
    def __init__(self, allen_vol_data):
        self.vol_data = allen_vol_data
        
    def __getitem__(self, some_slice):
        return self.vol_data.color_table[self.vol_data[some_slice],:]
    
    def plot_slides(self, coronal, sagittal, contour=True, ss=None, fig=None, return_figure=False):
            if fig is None:
                fig = plt.gcf()
            if ss is None:
                ss = plt.GridSpec(1,1)[0]
            if return_figure:
                fig.clear()
            gs = GridSpecFromSubplotSpec(1,2,subplot_spec=ss)
            ax = fig.add_subplot(gs[0])
            coronal_section = self[coronal,:,:]
            ax.imshow(coronal_section)
            coronal_section = self.vol_data[coronal,:,:]
            ax.axvline(sagittal, c='y',lw=1)
            if contour:
                for ix in range(self.vol_data.ids.shape[0]):
                    ith_contours = find_contours((coronal_section == ix).astype(float), 0.5)
                    for n_ith_contour in ith_contours:
                        plt.plot(n_ith_contour[:,1], n_ith_contour[:,0], lw=0.8,
                                 color="w")
            ax = fig.add_subplot(gs[1])
            sagittal_section = self[:,:,sagittal]
            ax.imshow(np.transpose(sagittal_section, (1,0,2)))
            sagittal_section = self.vol_data[:,:,sagittal]
            ax.axvline(coronal, c='y', lw=1)
            if contour:
                for ix in range(self.vol_data.ids.shape[0]):
                    ith_contours = find_contours((sagittal_section == ix).astype(float), 0.5)
                    for n_ith_contour in ith_contours:
                        plt.plot(n_ith_contour[:, 0], n_ith_contour[:, 1], lw=0.8, color="w")
            if return_figure:
                return fig