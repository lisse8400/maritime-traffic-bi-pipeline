CREATE TABLE data_chegada (
	id_data_chegada INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
	dia		 int,
	mes		 int,
	ano		 int,
	trimestre	 int,
	semestre	 int
);

CREATE TABLE barco (
	id_barco	 INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
	nome	 varchar(512),
	tipo	 varchar(512),
	capacidade int
);

CREATE TABLE condutor (
	id_condutor	 INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
	nome	 varchar(512),
	idade	 int,
	certificacao varchar(512)
);

CREATE TABLE origem (
	id_origem INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
	pais	 varchar(512),
	cidade	 varchar(512)
);

CREATE TABLE viagem (
	id_viagem			 INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
	valor_taxas			 float,
	peso_total_contentores	 float,
	num_contentores		 int,
	tipo_viagem			 varchar(512),
	data_partida		 date,
	origem_id_origem		 int NOT NULL,
	data_chegada_id_data_chegada int NOT NULL,
	condutor_id_condutor	 int NOT NULL,
	barco_id_barco		 int NOT NULL
);

ALTER TABLE viagem ADD CONSTRAINT viagem_fk1 FOREIGN KEY (origem_id_origem) REFERENCES origem(id_origem);
ALTER TABLE viagem ADD CONSTRAINT viagem_fk2 FOREIGN KEY (data_chegada_id_data_chegada) REFERENCES data_chegada(id_data_chegada);
ALTER TABLE viagem ADD CONSTRAINT viagem_fk3 FOREIGN KEY (condutor_id_condutor) REFERENCES condutor(id_condutor);
ALTER TABLE viagem ADD CONSTRAINT viagem_fk4 FOREIGN KEY (barco_id_barco) REFERENCES barco(id_barco);

