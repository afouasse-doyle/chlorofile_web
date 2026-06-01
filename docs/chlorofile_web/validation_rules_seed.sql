-- Seed appweb.validation_rules (regles conditionnelles nommees)
INSERT INTO appweb.validation_rules(rule_name,year_suffix,region,module,traitement,traitement_match,champ,rule_type,message) VALUES
('plant_ha_plantation','*','*','prescription','REB,REG','in','plant_ha','required','plant_ha requis pour REB/REG'),
('denombrement_cn_avt','*','CN','prescription','AVT','contains','denombrement_cn','required','Denombrement CN requis (AVT en region CN)'),
('traitement_ps_prep','*','*','prescription','DEBL,SCA','in','traitement_ps','required','Preparation de terrain requise (DEBL/SCA)'),
('taux_occ_andain_abit','*','ABIT','prescription','DEG,NET,EPC','in','taux_occ_andain','required','Taux occ. andain requis (DEG/NET/EPC en ABIT)');
