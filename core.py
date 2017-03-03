#!/usr/bin/env python
# encoding: utf-8

"""
Still need to do:
    -ambermini #how to do
"""

from __future__ import print_function, division 
# Python stdlib
import os
import subprocess
import tempfile
import shutil
# Chimera stuff
import chimera
from chimera import UserError
from MetalGeom import gui, Geometry  # I don't like this gui bare import. Too broad of a term that can easily pollute the namespace!
from chimera.molEdit import addAtom
from chimera import runCommand as rc

"""
This module contains the business logic of MetaDummy.
A GUI to apply cationc dummy atom method to systems
with one or more metal centers.
"""

class Controller(object):

    """
    The controller manages the communication between the UI (graphic interface)
    and the data model. Actions such as clicks on buttons, enabling certain areas, 
    or running external programs, are the responsibility of the controller.
    """

    def __init__(self, gui, model, *args, **kwargs):
        self.gui = gui
        self.model = model
        self.set_mvc()

    def set_mvc(self):
        self.gui.buttonWidgets['Run'].configure(command=self.run)

    def run(self):    

        print('Creating tmp directory...')
        tempdir = self.model.temp_directory()

    
        #Save last frame variables
        metal_menu = self.gui.ui_metals_menu
        self.model.save_variables(metal_menu.getvalue())

        #Start process for each metal
        metals = metal_menu.itemMap.values()
        for i, metal in enumerate(metals):

            # Get variables
            self.inputpath = metal_menu.getvalue().molecule.openedAs[0]
            self.res = str(metal.residue.type)
            self.name = str(metal.name)
            if self.inputpath.endswith(".pdb"):
                self.Type = str(metal.element.name)  
            elif self.inputpath.endswith(".mol2"):
                self.Type = str(metal.mol2type)
            else:
                raise UserError("No Valid Input File Type")
  
            #Retrieve metal parameters from gui
            self.model.retrieve_variables(metal)
   
            print("Building Metal Center...")
            metal_class = Metal.handle_atom_creation(metal=metal, Type=self.Type, 
                                                     res=self.res, model=self.model)

            print('Building dummies...')
            self.model.include_dummies(metal_class)

            print('Building Geometry...')
            self.model.specify_geometry(metal_class.residue, metal_class.symbol, 
                                        metal_class.center, metal_class.dummiespositions,
                                        tempdir)

            print('Creating library')
            self.model.creatlib(tempdir, metal_class.residue, i, 
                                self.model.gui.var_outputpath.get(), 
                                self.model.gui.var_outputname.get())
            
            print('Adding charges...')
            self.model.add_charge(tempdir, metal_class, self.name, i)
            
            print('Creating frcmod...')
            self.model.create_frcmod(temp_path=tempdir, metalmass=metal_class.mass,
                                     met=metal_class.symbol, i=i, 
                                     met_vwradius=metal_class.met_vwradius, 
                                     dz_met_bondlenght=metal_class.dz_met_bondlenght,
                                     dzmass= metal_class.dzmass)

            print('Metal Center Finished Deleting temp Files')
          

        print('Saving system...')
        self.model.create_system(inputpath=self.inputpath, temp_path=tempdir,
                                 met=metal_class.symbol, i=i, 
                                 output=self.gui.var_outputpath.get(),
                                 output_name=self.model.gui.var_outputname.get())


class Model(object):

    """
    Proper description of the model!
    """

    def __init__(self, gui, *args, **kwargs):
        self.gui = gui
        self.lib = []
        self.frcmod = []
        self.tempfiles = []

    def save_variables(self, metal):

        """
        Save last minute change variables made by client
        and retrieve GUI variables.

        Parameters:
        ------------
        metal: chimera object
            Metal Center
        """

        #Saving last metal params
        metal_dicts = self.gui.metals

        # [Note 1]
        # You are iterating metal_dicts once just to see if you should iterate
        # over it... Just do it from the beginning. If the if clause does not
        # returns True, nothing will happen, and that's fine
        if any(dic["title"] == metal.name for dic in metal_dicts):
            for dic in metal_dicts:
                if dic["title"] == metal.name:
                    dic["geom"] = self.gui.var_metal_geometry.get()
                    dic["charge"] =  self.gui.var_metal_charge.get()
                    dic["vw_radius"] = self.gui.var_vw_radius.get()
                    dic["dz_mass"] = self.gui.var_dz_mass.get()
                    dic["dz_met_bond"] = self.gui.var_dz_met_bondlenght.get()
        # Same here [Note 1]
        elif not any(dic["title"] == metal.name for dic in metal_dicts):
            dic = {}
            dic["title"] = metal.name
            dic["geom"] = self.gui.var_metal_geometry.get()
            dic["charge"] =  self.gui.var_metal_charge.get()
            dic["vw_radius"] = self.gui.var_vw_radius.get()
            dic["dz_mass"] = self.gui.var_dz_mass.get()
            dic["dz_met_bond"] = self.gui.var_dz_met_bondlenght.get()
            metal_dicts.append(dic)


    def retrieve_variables(self, metal):
        #Updating variables for each metal
        metal_dicts = self.gui.metals
        # Same here [Note 1]
        if any(dic["title"] == metal.name for dic in metal_dicts):
            for dic in metal_dicts:
                if dic["title"] == metal.name:
                    self.geometry = dic["geom"]
                    self.charge = dic["charge"]
                    self.vw_radius = dic["vw_radius"]
                    self.dz_mass = dic["dz_mass"] 
                    self.dz_met = dic["dz_met_bond"]
        # Same here [Note 1]
        elif not any(dic["title"] == metal.name for dic in metal_dicts): 
            self.geometry = "tetrahedral"
            self.charge = 2
            self.vw_radius = 3.1
            self.dz_mass = 3 
            self.dz_met = 0.9

    def temp_directory(self):

        """
        Create Temporary Directory

        Output:
        -------
        Temporary Folder Path
        """

        if os.path.isdir("/dev/shm/"):
            ram_dir = "/dev/shm/temp/"
            os.makedirs(ram_dir)
            self.tempdir = ram_dir
        else:
            self.tempdir = tempfile.mkdtemp(prefix="Dummy")
        return self.tempdir

    def include_dummies(self, metal_class):
        """
        docstring please
        """
        #Find metal coord
        dummy_names=[]
        dummiespositions = []
        metal = metal_class.metal    
        coord = metal.coord()
        for vec in metal_class.vecs:
            vec.length = self.dz_met
            metal_center=chimera.Vector(coord[0],coord[1],coord[2])
            dummyposition =  metal_center + vec
            dummiespositions.append(dummyposition)

        #Include dummies
        chain = metal.residue.id.chainId
        res = metal.residue
        mol = metal.molecule
        pos = 1
        # Are you counting residues? Try with mol.numResidues.
        while mol.findResidue(chimera.MolResId(chain, pos)):
            pos += 1
        dummy_element = chimera.Element('DZ')

        # Multi-or checks are cleaner with `in`
        if self.geometry in ('tetrahedral', 'square planar'):
            dummy_names = ["D1", "D2", "D3", "D4"]  
        elif self.geometry == 'octahedral':
            dummy_names = ["D1", "D5", "D2", "D3", "D6", "D4"]
        elif self.geometry == 'square pyramid':
            dummy_names = ["D1", "D5", "D2", "D3", "D4"] 
        else:
            # In case of errors? What do we do?
            pass

        for i, dummy_name in enumerate(dummy_names): 
            # esta te ha gustado, a que si...
            dummy_coord = chimera.Coord(*dummiespositions[i][0:3])
            addAtom(dummy_name, dummy_element, res, dummy_coord) 

    def specify_geometry(self, res, met, metal, dum, temp_path):
        
        """
        Create a pdb file including a metal center and 4 dummy atoms in tetrahedral geometry.

        Parameters
        ----------
        res: str
            Metal residue Name
        met: str
            Metal Symbol
        Metal: str
            Metal object
        dum: list (matrix)
            Dummy Oriented Positions
        temp_path: str
            temp directory path

        """
        # Wow, just wow. I am sure you are able to do this better, and cleaner.
        # Use a template string and then iterate with for and zip!
        filename = os.path.join(temp_path,"dummymetal.pdb")
        self.tempfiles.append(filename)
        with open(filename, 'w') as f:
            if self.geometry == 'tetrahedral':
        
                f.write("HETATM    1  %s  %s    1      %.3f  %.3f  %.3f  1.00           %s\n" %(met, res, metal[0], metal[1], metal[2] ,met))
                f.write("HETATM    2  D1  %s    1      %.3f  %.3f  %.3f  1.00           DZ\n" %(res, dum[0][0], dum[0][1], dum[0][2]))
                f.write("HETATM    3  D2  %s    1      %.3f  %.3f  %.3f  1.00           DZ\n" %(res, dum[1][0], dum[1][1], dum[1][2]))
                f.write("HETATM    4  D3  %s    1      %.3f  %.3f  %.3f  1.00           DZ\n" %(res, dum[2][0], dum[2][1], dum[2][2]))
                f.write("HETATM    5  D4  %s    1      %.3f  %.3f  %.3f  1.00           DZ\n" %(res, dum[3][0], dum[3][1], dum[3][2]))
                f.write("END")

            elif self.geometry == 'octahedral':
                f.write("HETATM    1  %s  %s    1      %.3f  %.3f  %.3f  1.00           %s\n" %(met, res, metal[0], metal[1], metal[2], met))
                f.write("HETATM    2  D1  %s    1      %.3f  %.3f  %.3f  1.00           DX\n" %(res, dum[0][0], dum[0][1], dum[0][2]))
                f.write("HETATM    3  D2  %s    1      %.3f  %.3f  %.3f  1.00           DY\n" %(res, dum[2][0], dum[2][1], dum[2][2]))
                f.write("HETATM    4  D3  %s    1      %.3f  %.3f  %.3f  1.00           DY\n" %(res, dum[3][0], dum[3][1], dum[3][2]))
                f.write("HETATM    5  D4  %s    1      %.3f  %.3f  %.3f  1.00           DX\n" %(res, dum[5][0], dum[5][1], dum[5][2]))
                f.write("HETATM    6  D5  %s    1      %.3f  %.3f  %.3f  1.00           DZ\n" %(res, dum[1][0], dum[1][1], dum[1][2]))
                f.write("HETATM    7  D6  %s    1      %.3f  %.3f  %.3f  1.00           DZ\n" %(res, dum[4][0], dum[4][1], dum[4][2]))
                f.write("END")

            elif self.geometry == 'square planar':      
                f.write("HETATM    1  %s  %s    1      %.3f  %.3f  %.3f  1.00           %s\n" %(met, res, metal[0], metal[1], metal[2] ,met))
                f.write("HETATM    2  D1  %s    1      %.3f  %.3f  %.3f  1.00           DY\n" %(res, dum[0][0], dum[0][1], dum[0][2]))
                f.write("HETATM    3  D2  %s    1      %.3f  %.3f  %.3f  1.00           DY\n" %(res, dum[1][0], dum[1][1], dum[1][2]))
                f.write("HETATM    4  D3  %s    1      %.3f  %.3f  %.3f  1.00           DX\n" %(res, dum[2][0], dum[2][1], dum[2][2]))
                f.write("HETATM    5  D4  %s    1      %.3f  %.3f  %.3f  1.00           DX\n" %(res, dum[3][0], dum[3][1], dum[3][2]))
                f.write("END")

            elif self.geometry == 'square pyramid':      
                f.write("HETATM    1  %s  %s    1      %.3f  %.3f  %.3f  1.00           %s\n" %(met, res, metal[0], metal[1], metal[2] ,met))
                f.write("HETATM    2  D1  %s    1      %.3f  %.3f  %.3f  1.00           DY\n" %(res, dum[0][0], dum[0][1], dum[0][2]))
                f.write("HETATM    3  D2  %s    1      %.3f  %.3f  %.3f  1.00           DY\n" %(res, dum[1][0], dum[1][1], dum[1][2]))
                f.write("HETATM    4  D3  %s    1      %.3f  %.3f  %.3f  1.00           DX\n" %(res, dum[2][0], dum[2][1], dum[2][2]))
                f.write("HETATM    5  D4  %s    1      %.3f  %.3f  %.3f  1.00           DX\n" %(res, dum[3][0], dum[3][1], dum[3][2]))
                f.write("HETATM    6  D5  %s    1      %.3f  %.3f  %.3f  1.00           DZ\n" %(res, dum[4][0], dum[4][1], dum[4][2]))
                f.write("END")

    # Funny method name... create_lib, maybe?
    def creatlib(self, temp_path, res, i, output, output_name): # ambermini

        """
        Creates a leaprc file. When we run that one in xleap,
        the program will create a file called met.lib 
        where we'll have information about 
        our metal center and 4 dummy atoms with connectivity missing.

        Parameters
        ----------
        temp_path: str
            Location of the folder amber14 in your computer
        res: str
            Metal Residue name
        i: int
            Metal number
        output: str
            Desired Output Path
        output_name: str
            Desires output name
        """
        # try should only include the critical parts...
        pdbfile = os.path.join(temp_path, "dummymetal.pdb")
        filename = os.path.join(temp_path, "leaprc.metal")
        output_lib = os.path.join(temp_path, "met%d.lib" % i)
        self.tempfiles.append(filename)
        lib_filename = os.path.join(temp_path, "met%d.lib" % i)
        # what is this '\n' for... in the filenameeeee!
        source = os.path.join(temp_path, "/dat/leap/cmd/oldff/leaprc.ff99SB\n")
        try:
            with open(filename, 'w') as f:
                f.write("logFile leap.log\n")
                f.write("source " + source)
                f.write("%s= loadpdb %s\n"%(res,pdbfile))
                f.write("saveoff %s %s\n"%(res,output_lib))
                f.write("quit")
        except IOError:
            # This type of exception masking is not very useful, actually
            raise UserError("Impossible to open leaprc file")
        
        # Hardcoded paths are worst thing ever. Get rid of that ASAP
        # If amberhome is not set, raise an error, but don't do this, please.
        # Anyway, this sould be set at __init__, not here, lost in non-related logic.
        self.amber_path = os.environ['AMBERHOME'] =  "/home/daniel/Baixades/amber14"
        # command should be a list of items, not a string
        command = "$AMBERHOME/bin/tleap -s -f %s" % filename
               
        log_file = os.path.join(output, output_name + ".log")
        with open(log_file, 'w') as log:
            # shell = True... give me a good reason.
            subprocess.call(command, stdout=log, stderr=log, shell=True)
        self.lib.append(lib_filename)

    def add_charge(self, temp_path, metal, name, i):
        """
        Nasty but easy and simple way to include the charge
        and connectivity inside the .lib file created before.

        Parameters
        ----------
        temp_path: str
            Temp Folder Path
        metal:Chimera obj
            Metal
        name:str
            Metal name
        i: int
            Metal Number
        """
        # I am about to puke. You know it's nasty, so don't do that.
        # Rewrite this elegantly, please.

        q = metal.charge
        met = metal.symbol
        atm = metal.atomicnumber
        res = metal.residue        

        if self.geometry == 'tetrahedral':
            lineas=[]
            try:
                file = open("%s/met%d.lib"%(temp_path,i),"r")
                lineas=list(file)
                lineas[3]=' "%s" "%s" 0 1 196609 1 %d 0.0\n'%(name,met,atm)
                lineas[4]=' "D1" "DZ" 0 1 196609 2 -1 %.5f\n'%(q/4.0)
                lineas[5]=' "D2" "DZ" 0 1 196609 3 -1 %.5f\n'%(q/4.0)
                lineas[6]=' "D3" "DZ" 0 1 196609 4 -1 %.5f\n'%(q/4.0)
                lineas[7]=' "D4" "DZ" 0 1 196609 5 -1 %.5f\n'%(q/4.0)
                lineas[9]=' "%s" "%s" 0 -1 0.0\n'%(name,met)
                lineas[10]=' "D1" "DZ" 0 -1 0.0\n'
                lineas[11]=' "D2" "DZ" 0 -1 0.0\n'
                lineas[12]=' "D3" "DZ" 0 -1 0.0\n'
                lineas[13]=' "D4" "DZ" 0 -1 0.0\n'
                lineas.insert(25,'!entry.%s.unit.connectivity table  int atom1x  int atom2x  int flags\n'%res)
                lineas.insert(26,' 1 3 1\n')
                lineas.insert(27,' 1 2 1\n')
                lineas.insert(28,' 1 4 1\n')
                lineas.insert(29,' 1 5 1\n')
                lineas.insert(30,' 2 3 1\n')
                lineas.insert(31,' 2 4 1\n')
                lineas.insert(32,' 2 5 1\n')
                lineas.insert(33,' 3 5 1\n')
                lineas.insert(34,' 3 4 1\n')
                lineas.insert(35,' 4 5 1\n')
                file.close()

                filename = "%s/met%d.lib"%(temp_path,i)
                with open(filename,"w") as f:
                    for linea in lineas:
                        
                        #if linea==lineas[25]:
                        #    f.write("!entry.mm.unit.connectivity table  int atom1x  int atom2x  int flags\n 1 3 1\n 1 2 1\n 1 4 1\n 1 5 1\n 2 3 1\n 2 4 1\n 2 5 1\n 3 5 1\n 3 4 1\n 4 5 1\n"%(RES))    
                        f.write(linea)

            except IOError:
                print('Impossible to open .lib file')

        elif self.geometry == 'octahedral':
            lineas=[]
            try:
                file = open("%s/met%d.lib"%(temp_path,i),"r")
                lineas=list(file)
                lineas[3]=' "%s" "%s" 0 1 196609 1 %d 0.0\n'%(name,met,atm)
                lineas[4]=' "D1" "DX" 0 1 196609 2 -1 %.5f\n'%(q/6.0)
                lineas[5]=' "D2" "DY" 0 1 196609 3 -1 %.5f\n'%(q/6.0)
                lineas[6]=' "D3" "DY" 0 1 196609 4 -1 %.5f\n'%(q/6.0)
                lineas[7]=' "D4" "DX" 0 1 196609 5 -1 %.5f\n'%(q/6.0)
                lineas[8]=' "D5" "DZ" 0 1 196609 6 -1 %.5f\n'%(q/6.0)
                lineas[9]=' "D6" "DZ" 0 1 196609 7 -1 %.5f\n'%(q/6.0)
                lineas[11]=' "%s" "%s" 0 -1 0.0\n'%(name,met)
                lineas[12]=' "D1" "DX" 0 -1 0.0\n'
                lineas[13]=' "D2" "DY" 0 -1 0.0\n'
                lineas[14]=' "D3" "DY" 0 -1 0.0\n'
                lineas[15]=' "D4" "DX" 0 -1 0.0\n'
                lineas[16]=' "D5" "DZ" 0 -1 0.0\n'
                lineas[17]=' "D6" "DZ" 0 -1 0.0\n'
                lineas.insert(29,'!entry.%s.unit.connectivity table  int atom1x  int atom2x  int flags\n'%res)
                lineas.insert(30, ' 1 5 1\n')
                lineas.insert(31, ' 1 2 1\n')
                lineas.insert(32, ' 2 6 1\n')
                lineas.insert(33, ' 2 4 1\n')
                lineas.insert(34, ' 6 5 1\n')
                lineas.insert(35, ' 4 5 1\n')
                lineas.insert(36, ' 7 2 1\n')
                lineas.insert(37, ' 5 3 1\n')
                lineas.insert(38, ' 3 2 1\n')
                lineas.insert(39, ' 7 5 1\n')

                file.close()

                filename = os.path.join(temp_path,"/met%d.lib"%i)
                with open(filename,"w") as f:
                    for linea in lineas:
                        #if linea==lineas[25]:
                        #    f.write("!entry.mm.unit.connectivity table  int atom1x  int atom2x  int flags\n 1 3 1\n 1 2 1\n 1 4 1\n 1 5 1\n 2 3 1\n 2 4 1\n 2 5 1\n 3 5 1\n 3 4 1\n 4 5 1\n"%(RES))    
                        f.write(linea)

            except IOError:
                raise UserError("Impossible to open .lib file")

        elif self.geometry == 'square planar':
            lineas=[]
            try:
                file = open("%s/met%d.lib"%(temp_path,i),"r")
                lineas=list(file)
                lineas[3]=' "%s" "%s" 0 1 196609 1 %d 0.0\n'%(name,met,atm)
                lineas[4]=' "D1" "DY" 0 1 196609 2 -1 %.5f\n'%(q/4.0)
                lineas[5]=' "D2" "DY" 0 1 196609 3 -1 %.5f\n'%(q/4.0)
                lineas[6]=' "D3" "DX" 0 1 196609 4 -1 %.5f\n'%(q/4.0)
                lineas[7]=' "D4" "DX" 0 1 196609 5 -1 %.5f\n'%(q/4.0)
                lineas[9]=' "%s" "%s" 0 -1 0.0\n'%(name,met)
                lineas[10]=' "D1" "DY" 0 -1 0.0\n'
                lineas[11]=' "D2" "DY" 0 -1 0.0\n'
                lineas[12]=' "D3" "DX" 0 -1 0.0\n'
                lineas[13]=' "D4" "DX" 0 -1 0.0\n'
                lineas.insert(25,'!entry.%s.unit.connectivity table  int atom1x  int atom2x  int flags\n'%res)
                lineas.insert(26,' 1 3 1\n')
                lineas.insert(27,' 1 2 1\n')
                lineas.insert(28,' 1 4 1\n')
                lineas.insert(29,' 1 5 1\n')
                lineas.insert(30,' 2 5 1\n')
                lineas.insert(31,' 5 3 1\n')
                lineas.insert(32,' 3 4 1\n')
                lineas.insert(33,' 4 2 1\n')
                file.close()

                filename = "%s/met%d.lib"%(temp_path,i)
                with open(filename,"w") as f:
                    for linea in lineas:    
                        f.write(linea)

            except IOError:
                print('Impossible to open .lib file')

        elif self.geometry == 'square pyramid':
            lineas=[]
            try:
                file = open("%s/met%d.lib"%(temp_path,i),"r")
                lineas=list(file)
                lineas[3]=' "%s" "%s" 0 1 196609 1 %d 0.0\n'%(name,met,atm)
                lineas[4]=' "D1" "DY" 0 1 196609 2 -1 %.5f\n'%(q/5.0)
                lineas[5]=' "D2" "DY" 0 1 196609 3 -1 %.5f\n'%(q/5.0)
                lineas[6]=' "D3" "DX" 0 1 196609 4 -1 %.5f\n'%(q/5.0)
                lineas[7]=' "D4" "DX" 0 1 196609 5 -1 %.5f\n'%(q/5.0)
                lineas[8]=' "D5" "DZ" 0 1 196609 6 -1 %.5f\n'%(q/5.0)
                lineas[10]=' "%s" "%s" 0 -1 0.0\n'%(name,met)
                lineas[11]=' "D1" "DY" 0 -1 0.0\n'
                lineas[12]=' "D2" "DY" 0 -1 0.0\n'
                lineas[13]=' "D3" "DX" 0 -1 0.0\n'
                lineas[14]=' "D4" "DX" 0 -1 0.0\n'
                lineas[15]=' "D5" "DZ" 0 -1 0.0\n'
                lineas.insert(27,'!entry.%s.unit.connectivity table  int atom1x  int atom2x  int flags\n'%res)
                lineas.insert(28,' 1 3 1\n')
                lineas.insert(29,' 1 2 1\n')
                lineas.insert(30,' 1 4 1\n')
                lineas.insert(31,' 1 5 1\n')
                lineas.insert(32,' 2 5 1\n')
                lineas.insert(33,' 5 3 1\n')
                lineas.insert(34,' 3 4 1\n')
                lineas.insert(35,' 4 2 1\n')
                file.close()

                filename = "%s/met%d.lib"%(temp_path,i)
                with open(filename,"w") as f:
                    for linea in lineas:    
                        f.write(linea)
            except IOError:
                print('Impossible to open .lib file')

    def create_frcmod(self, temp_path, metalmass, dzmass, dz_met_bondlenght, met_vwradius, met,i):
        
        """
        Creates a frcmod containig all the parameters about
        the connectivity of our metal center for each Geom.
        (Bonds and angles for met-met and met-Dummy)

        Parameters
        ----------
        temp_path: str
            Temp Folder Path
        metalmass: int
            Metal mass
        dzmass: int
            Dummies mass
        dz_met_bondlenght: int
            Metal-Dummy lenght bond
        met_vwradius:
            VW metal radius
        met: str
            Metal symbol
        i: int
            Metal number
        """
        # Same here....
        try:
            frcmod_filename = os.path.join(temp_path,"zinc%d.frcmod"%i)
            with open(frcmod_filename,"w") as f:

                if self.geometry == 'tetrahedral':
                    f.write("Amber Force Field Parameters for a Cathionic Dummy Atoms Method\n")
                    f.write("MASS\nDZ  %.3f\n%s %.2f\n\n"%(dzmass, met, metalmass-dzmass*4))
                    f.write("BOND\nDZ-%s  640.0    %.3f\nDZ-DZ  640.0    1.47\n\n"%(met, dz_met_bondlenght))
                    f.write("ANGLE\nDZ-%s-DZ    55.0      109.50\nDZ-DZ-DZ    55.0       60.0\nDZ-DZ-%s    55.0       35.25\n\n"%(met,met))
                    f.write("DIHE\n%s-DZ-DZ-DZ   1    0.0          35.3             2.00\nDZ-%s-DZ-DZ   1    0.0         120.0             2.00\nDZ-DZ-DZ-DZ   1    0.0          70.5             2.00\n\n"%(met,met))
                    f.write("IMPROPER\n\n")
                    f.write("NONB\nDZ          0.000   0.00\n%s          %.3f   1.0E-6"%(met, met_vwradius ))
                    f.write("")

                elif self.geometry == 'octahedral':
                    f.write("Amber Force Field Parameters for a Cathionic Dummy Atoms Method\n")
                    f.write("MASS\nDX  %.3f\n"%(dzmass))
                    f.write("DY  %.3f\n"%(dzmass))
                    f.write("DZ  %.3f\n%s %.2f\n\n"%(dzmass, met, metalmass-dzmass*6))
                    f.write("BOND\n")
                    f.write("%s-DX  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("%s-DY  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("%s-DZ  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("DX-DY  640      1.273\n")
                    f.write("DX-DZ  640      1.273\n")
                    f.write("DY-DZ  640      1.273\n\n")
                    f.write("ANGL\n")
                    f.write("DX-%s-DX    55.0      180.00\n"%(met))
                    f.write("DY-%s-DY    55.0      180.00\n"%(met))
                    f.write("DZ-%s-DZ    55.0      180.00\n"%(met))
                    f.write("DX-%s-DY    55.0      90.00\n"%(met))
                    f.write("DX-%s-DZ    55.0      90.00\n"%(met))
                    f.write("DY-%s-DZ    55.0      90.00\n"%(met))
                    f.write("%s-DX-DY    55.0      45.00\n"%(met))
                    f.write("%s-DX-DZ    55.0      45.00\n"%(met))
                    f.write("%s-DY-DZ    55.0      45.00\n"%(met))
                    f.write("DX-DY-DX    55.0      90.00\n")
                    f.write("DX-DZ-DX    55.0      90.00\n")
                    f.write("DY-DX-DY    55.0      90.00\n")
                    f.write("DZ-DX-DZ    55.0      90.00\n")
                    f.write("DY-DZ-DY    55.0      90.00\n")
                    f.write("DY-DX-DZ    55.0      60\n")
                    f.write("DX-DY-DZ    55.0      60\n")
                    f.write("DX-DZ-DY    55.0      60\n\n")
                    f.write("DIHE\n")
                    f.write("DX-%s-DX-DZ  4   0.0    0.0    1.\n"%(met))
                    f.write("DX-DY-DX-DZ  4   0.0    0.0    1.\n")
                    f.write("DX-DZ-DX-DZ  4   0.0    0.0    1.\n")
                    f.write("DY-DX-DZ-DX  4   0.0    0.0    1.\n")
                    f.write("DY-DX-%s-DX  4   0.0    0.0    1.\n"%(met)) 
                    f.write("DX-%s-DX-DY  4   0.0    0.0    1.\n"%(met)) 
                    f.write("DY-DX-DY-DX  4   0.0    0.0    1.\n")
                    f.write("%s-DX-DY-DX  4   0.0    0.0    1.\n"%(met))
                    f.write("%s-DX-DZ-DX  4   0.0    0.0    1.\n"%(met)) 
                    f.write("DX-DY-DX-DY  4   0.0    0.0    1.\n\n")
                    f.write("IMPR\n\n")
                    f.write("NONB\n")
                    f.write("  %s          %.3f   1.0E-6\n"%(met, met_vwradius ))
                    f.write("  DX          0.0000  0.0000\n")
                    f.write("  DY          0.0000  0.0000\n")
                    f.write("  DZ          0.0000  0.0000\n\n")
                    f.write("")
                    #f.write("  DX          0.7671  0.0125\n")
                    #f.write("  DY          0.7671  0.0125\n")
                    #f.write("  DZ          0.7671  0.0125\n\n")

                elif self.geometry == 'square planar':
                    f.write("Amber Force Field Parameters for a Cathionic Dummy Atoms Method\n")
                    f.write("MASS\nDX  %.3f\n"%(dzmass))
                    f.write("DY  %.3f\n"%(dzmass))
                    f.write("%s %.2f\n\n"%(met, metalmass-dzmass*4))
                    f.write("\nBOND\n")
                    f.write("%s-DX  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("%s-DY  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("DX-DY  640      1.273\n")
                    f.write("\nANGL\n")
                    f.write("DX-%s-DX    55.0      180.00\n"%(met))
                    f.write("DY-%s-DY    55.0      180.00\n"%(met))
                    f.write("DX-%s-DY    55.0      90.00\n"%(met))
                    f.write("%s-DX-DY    55.0      45.00\n"%(met))
                    f.write("%s-DY-DX    55.0      45.00\n"%(met))
                    f.write("DX-DY-DX    55.0      90.00\n")
                    f.write("DX-DZ-DX    55.0      90.00\n")
                    f.write("DY-DX-DY    55.0      90.00\n")
                    f.write("\nDIHE\n")
                    f.write("%s-DY-DX-DY  4   0.0    0.0    1.\n"%(met))
                    f.write("DX-DY-%s-DX  4   0.0    0.0    1.\n"%(met))
                    f.write("DY-DX-%s-DY  4   0.0    0.0    1.\n"%(met))
                    f.write("DY-DX-%s-DX  4   0.0    0.0    1.\n"%(met))
                    f.write("DX-%s-DY-DX  4   0.0    0.0    1.\n"%(met))
                    f.write("DY-%s-DY-DX  4   0.0    0.0    1.\n"%(met))
                    f.write("DY-%s-DX-DY  4   0.0    0.0    1.\n"%(met))    
                    f.write("DY-DX-DY-DX  4   0.0    0.0    1.\n")
                    f.write("%s-DX-DY-DX  4   0.0    0.0    1.\n"%(met))
                    f.write("DX-DY-DX-DY  4   0.0    0.0    1.\n\n")
                    f.write("IMPR\n\n")
                    f.write("NONB\n")
                    f.write("  %s          %.3f   1.0E-6\n"%(met, met_vwradius ))
                    f.write("  DX          0.0000  0.000\n")
                    f.write("  DY          0.0000  0.000\n")
                    f.write("")

                elif self.geometry == 'square pyramid':
                    f.write("BOND\n")
                    f.write("%s-DX  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("%s-DY  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("%s-DZ  640      %.3f\n"%(met, dz_met_bondlenght))
                    f.write("DX-DY  640      1.273\n")
                    f.write("DX-DZ  640      1.273\n")
                    f.write("DY-DZ  640      1.273\n\n")
                    f.write("ANGL\n")
                    f.write("DX-%s-DX    55.0      180.00\n"%(met))
                    f.write("DY-%s-DY    55.0      180.00\n"%(met))
                    f.write("DZ-%s-DZ    55.0      180.00\n"%(met))
                    f.write("DX-%s-DY    55.0      90.00\n"%(met))
                    f.write("DX-%s-DZ    55.0      90.00\n"%(met))
                    f.write("DY-%s-DZ    55.0      90.00\n"%(met))
                    f.write("%s-DX-DY    55.0      45.00\n"%(met))
                    f.write("%s-DX-DZ    55.0      45.00\n"%(met))
                    f.write("%s-DY-DZ    55.0      45.00\n"%(met))
                    f.write("DX-DY-DX    55.0      90.00\n")
                    f.write("DX-DZ-DX    55.0      90.00\n")
                    f.write("DY-DX-DY    55.0      90.00\n")
                    f.write("DZ-DX-DZ    55.0      90.00\n")
                    f.write("DY-DZ-DY    55.0      90.00\n")
                    f.write("DY-DX-DZ    55.0      60\n")
                    f.write("DX-DY-DZ    55.0      60\n")
                    f.write("DX-DZ-DY    55.0      60\n\n")
                    f.write("DIHE\n")
                    f.write("DX-%s-DX-DZ  4   0.0    0.0    1.\n"%(met))
                    f.write("DX-DY-DX-DZ  4   0.0    0.0    1.\n")
                    f.write("DX-DZ-DX-DZ  4   0.0    0.0    1.\n")
                    f.write("DY-DX-DZ-DX  4   0.0    0.0    1.\n")
                    f.write("DY-DX-%s-DX  4   0.0    0.0    1.\n"%(met)) 
                    f.write("DX-%s-DX-DY  4   0.0    0.0    1.\n"%(met)) 
                    f.write("DY-DX-DY-DX  4   0.0    0.0    1.\n")
                    f.write("%s-DX-DY-DX  4   0.0    0.0    1.\n"%(met))
                    f.write("%s-DX-DZ-DX  4   0.0    0.0    1.\n"%(met)) 
                    f.write("DX-DY-DX-DY  4   0.0    0.0    1.\n\n")
                    f.write("IMPR\n\n")
                    f.write("NONB\n")
                    f.write("  %s          %.3f   1.0E-6\n"%(met, met_vwradius ))
                    f.write("  DX          0.0000  0.0000\n")
                    f.write("  DY          0.0000  0.0000\n")
                    f.write("  DZ          0.0000  0.0000\n\n")
                    f.write("")

        except IOError:
            print("Impossible to open .frcmod file")

        self.frcmod.append(frcmod_filename)      

    def create_system(self, inputpath, temp_path, met, i, output, output_name):
       
        """
        System Creation through leaprc file:
            1-Charge Library
            2-Charge frcmod
            3-Build Water Box+
            4-System Neutralization

        Parameters
        ----------
        inputpath: str
            Input path File
        temp_path: str
            Temp Folder Path
        pdb: str
            Name of the pdb obtained by GAUDI
        met: str
            Metal symbol
        i: int
            Metal number
        output: str
            Output path
        output_name: str
            Output name
        
        Output:
        -------
        topology: prmtop
        coordinates: inpcrd
        """

        # Saving model
        if inputpath.endswith(".pdb"):
            Filename = self.gui.var_outputname.get() + '.pdb'
            pdb = os.path.join(self.tempdir, Filename)
            rc('write 0 ' + pdb)

        elif inputpath.endswith(".mol2"):
            Filename = self.gui.var_outputname.get() + '.mol2'
            mol2 = os.path.join(self.tempdir, Filename)
            rc("write format mol2 0 " + mol2)


        output_name = self.gui.var_outputname.get()
        filename = os.path.join(temp_path,"leaprc.final")
        with open(filename,"w") as f:
            f.write("logFile leap.log\n")
            f.write("source /home/daniel/leaprc\n")
            source = os.path.join(self.amber_path, "dat/leap/cmd/oldff/leaprc.ff99SB\n")
            f.write("source " + source)
            f.write("""addAtomTypes { { "DZ" "%s" "sp3" } { "%s" "%s" "sp3" } }\n"""%(met,met,met))
            f.write("""addAtomTypes {{ "DX" "%s" "sp3" } { "DY" "%s" "sp3" }}\n"""%(met,met)) 
            if self.frcmod:
                for frcmod in self.frcmod:
                    f.write("loadamberparams %s\n"%(frcmod))

            if self.lib:
                for lib in self.lib:
                    f.write("loadOff %s\n"%(lib))

            FilesToLoad = self.gui.ui_files_to_load.get(0,'end')
            if FilesToLoad:
                for file in list(FilesToLoad):
                    if file.endswith('.lib'):
                        f.write("loadOff %s\n"%(file))
                    elif file.endswith('.frcmod'):
                        f.write("loadamberparams %s\n"%(file))

            

            if inputpath.endswith(".pdb"):
                f.write("sys=loadpdb %s\n"%(pdb))
            elif inputpath.endswith(".mol2"):
                f.write("sys=loadmol2 %s\n"%(mol2))
            f.write("addIons sys Cl- 0\n")
            f.write("addIons sys Na+ 0\n")
            if self.gui.var_waterbox.get()==1:
                f.write("solvatebox sys TIP3PBOX 10\n")
            prmtop = os.path.join(output, output_name+".prmtop")
            inpcrd = os.path.join(output, output_name+".inpcrd")
            f.write("saveamberparm sys " + prmtop + " " + inpcrd + "\n")
            mol2 = os.path.join(output, output_name+".mol2")
            f.write("savemol2 sys " + mol2 + " 0\n")
            pdb = os.path.join(output, output_name+".pdb")
            f.write("savepdb sys " + pdb + "\n")
            f.write("")
        leaprc = os.path.join(temp_path, "leaprc.final")
        command = "$AMBERHOME/bin/tleap -s -f "+leaprc

        
        log_file = os.path.join(output, output_name + ".log")
        with open(log_file, 'a') as log:
            subprocess.call(command, stdout=log, stderr=log, shell=True)
        print('Program Finished')

        if os.path.exists(self.tempdir):
            print('Cleaning Memory')
            shutil.rmtree(self.tempdir)
        




# What kind of line length are you using? 200 chars? Trim that down to 100 or 100 tops.
############################################Elements#################################################

class Metal(Model):

    """
     A base class to build the best parameters
     to create the metal residue such as dummy
     orientationa and metal type.
    """

    def __init__(self, model, metal, symbol, atomicnumber, mass, residue):
        self.model = model
        self.symbol = symbol
        self.atomicnumber = atomicnumber
        self.mass = mass
        self.residue = residue
        self.charge = self.model.charge
        self.met_vwradius = self.model.vw_radius
        self.dzmass = self.model.dz_mass
        self.dz_met_bondlenght = self.model.dz_met
        self.metal = metal
        self.search_for_orientation(self.metal)
    
    def search_for_orientation(self, metal):

        """
        Search for lingands near by the metal center
        excluding candidates through the next steps:
            1-How many electrons on the outter shell
            2-Metal-Ligand distance
            3-Geometry angles
            4-Exclude Hydrogens and other atoms

        Parameters:
        -----------
        metal: chimera metal object

        Output:
        -------
        Dummies oriented positions 
        """

        # Don't you see a pattern here? Try with:
        # geom = Geometry.Geometry(self.model.geometry)
        if self.model.geometry == 'tetrahedral':
            geom = Geometry.Geometry('tetrahedral')
        elif self.model.geometry == 'octahedral':
            geom = Geometry.Geometry('octahedron')
        elif self.model.geometry == 'square planar':
            geom = Geometry.Geometry('square planar')
        elif self.model.geometry == 'square pyramid':
            geom = Geometry.Geometry('square pyramid')

        ligands = self.search_for_ligands(metal)
        print(len(ligands)) # debugging leftovers?
        rmsd, self.center, self.vecs = gui.geomDistEval(geom, metal, ligands)
        self.dummiespositions = []
        for vec in self.vecs:
            vec.length = self.dz_met_bondlenght
            dummyposition =  self.center + vec
            self.dummiespositions.append(dummyposition)
        return self.dummiespositions  # I don't like this name

    @staticmethod
    def search_for_ligands(metal):
        
        """
        Search for lingands near by the metal center
        excluding candidates through the next steps:
            1-How many electrons on the outter shell
            2-Metal-Ligand distance
            3-Geometry angles
            4-Exclude Hydrogens and other atoms

        Parameters:
        -----------
        metal: chimera metal object

        Output:
        -------
        chimera ligands object
        """
        # IMPORTS ALWAYS AT TOP OF THE FILE!!!!!!
        # Which Chimera file did you steal? :P
        data = []
        coordLim=4.0
        from numpy import array
        atoms = array(metal.molecule.atoms)
        from _multiscale import get_atom_coordinates as gac
        from _closepoints import find_close_points, BOXES_METHOD
        ignore, close = find_close_points(BOXES_METHOD,
            gac(array([metal])), gac(atoms), coordLim)
        candidates = list(set(atoms[close]))
        mcrd = metal.coord()
        candidates.sort(lambda a1, a2: cmp(a1.coord().sqdistance(mcrd),
                        a2.coord().sqdistance(mcrd)))
        exclude = []
        userIncluded = []
        for candidate in candidates:
            if candidate == metal:
                continue
            if candidate in exclude:
                continue
            if candidate not in userIncluded:
                valence = (candidate.element.number - 2) % 8
                if valence < 5 or candidate.element.number == 1:
                    continue
                if candidate.coord().distance(mcrd) > coordLim:
                    break
                if candidate not in metal.bondsMap:
                    from chimera import angle
                    from chimera.idatm import typeInfo
                    angleOK = True
                    try:
                        cnGeom = typeInfo[candidate.idatmType].geometry
                    except KeyError:
                        cnGeom = 0
                    else:
                        if len(candidate.primaryNeighbors()) == cnGeom:
                            # no lone pairs, no possibility of deprotonation
                            continue
                    angleCutoff = [0.0, 72.98, 120.0, 80.0, 72.98][cnGeom]
                    for cnb in candidate.neighbors:
                        if cnb == metal:
                            continue
                        if angle(cnb.coord(), candidate.coord(),
                                    metal.coord()) < angleCutoff:
                            angleOK = False
                            break
                    if not angleOK:
                        continue
            data.append(candidate)
        return data
    
    @classmethod    
    def handle_atom_creation(cls, metal, Type, res , model):

        """
        Handle metal creation by using a classmethod generator
        for each type of metal we can find on the input file.

        Parameters:
        -----------
        metal: chimera metal object
        Type: pdb/mol2 metal type
        res: metal residue name
        model: Modeller class

        Output:
        -------
        Metal class object 
        """
        # You know Chimera already includes this information, right?
        # It'd be enough with this:
        # return cls(model=model, metal=metal, symbol=Type, residue=res, 
        #            mass=metal.element.mass, atomicnumber=metal.element.number) 
        
        if str(metal.element.name).lower() == 'zn':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=30, mass=65.38, residue=res)   
        elif str(metal.element.name).lower() == 'fe':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=26, mass=55.845 , residue=res)
        elif str(metal.element.name).lower() == 'cd':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=48, mass=112.411, residue=res)
        elif str(metal.element.name).lower() == 'cu':
            return cls(model=model,  metal = metal, symbol=Type, atomicnumber=29, mass=63.546, residue=res)
        elif str(metal.element.name).lower() == 'co':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=27, mass=58.933, residue=res)
        elif str(metal.element.name).lower() == 'pt':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=78, mass=195.084, residue=res)
        elif str(metal.element.name).lower() == 'pd':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=46, mass=106.42, residue=res)
        elif str(metal.element.name).lower() == 'mg':
           return cls(model=model,metal = metal, symbol=Type, atomicnumber=12, mass=24.305, residue=res)
        elif str(metal.element.name).lower() == 'v':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=23, mass=50.9415, residue=res)
        elif str(metal.element.name).lower() == 'cr':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=24, mass=51.996, residue=res)
        elif str(metal.element.name).lower() == 'mn':
            return cls(model=model, metal = metal, symbol=Type, atomicnumber=25, mass=54.938, residue=res)
        else:
            pass#next???