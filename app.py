from flask import Flask, render_template, request
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem
import os
import pickle
from sklearn.impute import SimpleImputer

app = Flask(__name__)

### Load Models & Feature Sets
models_info = [
    {"name": "AZ_PC", "model_file": "AZ_PC.pkl", "feature_file": "feature_selection_lr_rfe_df_a_f.pkl"},
    {"name": "AZ_all", "model_file": "AZ_all.pkl", "feature_file": "feature_selection_lr_rfe_df_a_f_all.pkl"},
    {"name": "integrated_PC", "model_file": "integrated_PC.pkl", "feature_file": "feature_selection_brf_rfe_df_a_f.pkl"},
    {"name": "integrated_all", "model_file": "integrated_all.pkl", "feature_file": "feature_selection_brf_rfe_df_a_f_all.pkl"}
]

for model_info in models_info:
    with open(model_info["feature_file"], 'rb') as file:
        model_info["feature_set"] = pickle.load(file)
    with open(model_info["model_file"], 'rb') as file:
        model_info["model"] = pickle.load(file)

### **Flask Routes**
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    smiles_input = request.form['smiles']
    smiles_list = [s.strip() for s in smiles_input.split('\n') if s.strip()]
    
    # Convert SMILES to Canonical Form
    def to_canonical(smiles):
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            Chem.RemoveStereochemistry(mol)
            return Chem.MolToSmiles(mol, isomericSmiles=False)
        return None
    
    df_t = pd.DataFrame(smiles_list, columns=["Isomeric SMILES"])
    df_t["Canonical Smiles"] = df_t["Isomeric SMILES"].apply(to_canonical)
    df_t = df_t.drop_duplicates(subset="Canonical Smiles").reset_index(drop=True)
    
    # Generate SDF
    sdf_filename = "test5.sdf"
    writer = Chem.SDWriter(sdf_filename)
    
    for smiles in df_t["Canonical Smiles"]:
        molecule = Chem.MolFromSmiles(smiles)
        molecule = Chem.AddHs(molecule)
        AllChem.EmbedMultipleConfs(molecule, numConfs=50, useExpTorsionAnglePrefs=True, useBasicKnowledge=True)
        
        lowest_energy = float("inf")
        lowest_energy_confId = None
        
        for confId in range(molecule.GetNumConformers()):
            if AllChem.MMFFHasAllMoleculeParams(molecule):
                mmff_props = AllChem.MMFFGetMoleculeForceField(molecule, AllChem.MMFFGetMoleculeProperties(molecule), confId=confId)
                energy = mmff_props.CalcEnergy()
            else:
                uff_props = AllChem.UFFGetMoleculeForceField(molecule, confId=confId)
                energy = uff_props.CalcEnergy()
            
            if energy < lowest_energy:
                lowest_energy = energy
                lowest_energy_confId = confId
        
        if lowest_energy_confId is not None:
            writer.write(molecule, confId=lowest_energy_confId)
    writer.close()
    
    # Run PaDEL Descriptor
    output_csv = "test5_all_descriptors"
    xml_file = "fingerprints.xml"
    padel_jar = "PaDEL-Descriptor.jar"
    os.system(f'java -jar {padel_jar} -dir {sdf_filename} -file {output_csv} -2d -3d -fingerprints -retain3d -retainorder -detectaromaticity -standardizenitro -descriptortypes {xml_file}')
    
    test_data = pd.read_csv(output_csv)
    if 'Name' in test_data.columns:
        test_data = test_data.drop('Name', axis=1)
    
    imputer = SimpleImputer(strategy='mean')
    test_data = pd.DataFrame(imputer.fit_transform(test_data), columns=test_data.columns)
    
    # Run Predictions
    results_table = []
    for i, smiles in enumerate(df_t["Canonical Smiles"]):
        row = {"SMILES": smiles}
        for model_info in models_info:
            model_name = model_info["name"]
            X_test = test_data[model_info["feature_set"]]
            y_pred = model_info["model"].predict(X_test)
            y_prob = model_info["model"].predict_proba(X_test)[:, 1]
            
            row[f"{model_name}_class"] = y_pred[i]
            row[f"{model_name}_prob"] = round(y_prob[i], 4)
        
        results_table.append(row)
 
    return render_template('index.html', results=results_table)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))  # Use PORT from environment
    app.run(debug=True, host='0.0.0.0', port=port)
