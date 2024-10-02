from shiny import App, Inputs, Outputs, Session, reactive, render, ui, module
import alphatims.bruker as atb
import alphatims.plotting as atp
from collections import OrderedDict
from datetime import date
import io
import itertools
from itertools import groupby
import math
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.pyplot import cm
import matplotlib.colors as mcolors
from matplotlib.patches import Rectangle
from matplotlib_venn import venn2,venn2_circles,venn3,venn3_circles
import numpy as np
import os
import pandas as pd
import pathlib
import re
from scipy.stats import norm
import seaborn as sns
from tkinter import *
from upsetplot import *
from shinyswatch import theme
from faicons import icon_svg
#https://rstudio.github.io/shinythemes/
matplotlib.use('Agg')

# =============================================================================
# UI
# =============================================================================
#region

app_ui=ui.page_fluid(
    ui.panel_title("timsTOF Proteomics Data Visualization_v2024.09.13/Stable"),
    ui.navset_pill_list(
        ui.nav_panel("File Import",
                     ui.card(
                         ui.input_file("searchreport","Upload search report:",accept=".tsv",multiple=False),
                         ui.input_radio_buttons("software","Search software:",{"spectronaut":"Spectronaut","diann":"DIA-NN","ddalibrary":"DDA Library (Spectronaut)","timsdiann":"tims-DIANN (BPS)"}),
                         ui.output_text("metadata_reminder"),
                         ),
                     ui.card(
                         ui.card_header("Update from Metadata Table"),
                         ui.input_switch("condition_names","Update 'R.Condition' and 'R.Replicate' columns",width="100%"),
                         ui.input_switch("concentration","Update 'Concentration' column",width="100%"),
                         ui.input_switch("remove_resort","Remove/resort samples"),
                         ui.input_action_button("rerun_metadata","Apply changes to search report / reinitialize search report",width="300px",class_="btn-primary")
                         ),
                     ui.card(
                         ui.card_header("Metadata Table"),
                         ui.p("-Double click on any cell to update its contents"),
                         ui.p("-To remove samples, add an 'x' to the 'remove' column. To reorder samples, number them in the order you want them to appear in the 'order' column"),
                         ui.output_data_frame("metadata_table")
                     ),icon=icon_svg("folder-open")
                    ),
        ui.nav_panel("Settings",
                     ui.navset_pill(
                         ui.nav_panel("Color Settings",
                                      ui.row(ui.column(4,
                                                       ui.input_radio_buttons("coloroptions","Choose coloring option for output plots:",choices={"pickrainbow":"Pick for me (rainbow)","pickmatplot":"Pick for me (matplotlib tableau)","custom":"Custom"},selected="pickmatplot"),
                                                       ui.input_text_area("customcolors","Input color names from the tables to the right, one per line:",autoresize=True),
                                                       ui.output_text("colornote"),
                                                       ui.row(ui.column(4,
                                                                        ui.output_table("customcolors_table1")
                                                                        ),
                                                              ui.column(4,
                                                                        ui.output_table("conditioncolors"),
                                                                        ui.output_plot("customcolors_plot")
                                                                        )
                                                              )
                                                       ),
                                             ui.column(2,
                                                       ui.output_text("matplotlibcolors_text"),ui.output_plot("matplotlibcolors")
                                                       ),
                                             ui.column(5,
                                                       ui.output_text("csscolors_text"),ui.output_plot("csscolors")
                                                       ),
                                             )
                                      ),
                         ),icon=icon_svg("gear")
                     ),
        ui.nav_panel("ID Counts",
                     ui.navset_pill(
                         ui.nav_panel("Counts per Condition",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("idmetrics_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("idmetrics_height","Plot height",min=500,max=2000,step=100,value=1000,ticks=True)
                                              )
                                              ),
                                      ui.input_selectize("idplotinput","Choose what metric to plot:",choices={"all":"all","proteins":"proteins","proteins2pepts":"proteins2pepts","peptides":"peptides","precursors":"precursors"},multiple=False,selected="all"),
                                      ui.output_plot("idmetricsplot")
                                    ),
                         ui.nav_panel("Average Counts",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("avgidmetrics_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("avgidmetrics_height","Plot height",min=500,max=2000,step=100,value=1000,ticks=True)
                                              )
                                              ),
                                      ui.input_selectize("avgidplotinput","Choose what metric to plot:",choices={"all":"all","proteins":"proteins","proteins2pepts":"proteins2pepts","peptides":"peptides","precursors":"precursors"},multiple=False,selected="all"),
                                      ui.output_plot("avgidmetricsplot")
                                    ),
                         ui.nav_panel("CV Plots",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("cvplot_width","Plot width",min=100,max=2000,step=100,value=1000,ticks=True),
                                              ui.input_slider("cvplot_height","Plot height",min=100,max=2000,step=100,value=500,ticks=True)
                                              )
                                            ),
                                      ui.row(
                                          ui.input_radio_buttons("proteins_precursors_cvplot","Pick which IDs to plot",choices={"Protein":"Protein","Precursor":"Precursor"}),
                                          ui.input_switch("removetop5percent","Remove top 5%")
                                          ),
                                      ui.output_plot("cvplot")
                                      ),
                         ui.nav_panel("IDs with CV Cutoff",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("countscvcutoff_width","Plot width",min=500,max=2000,step=100,value=900,ticks=True),
                                              ui.input_slider("countscvcutoff_height","Plot height",min=500,max=2000,step=100,value=700,ticks=True)
                                            )
                                          ),
                                      ui.input_radio_buttons("proteins_precursors_idcutoffplot","Pick which IDs to plot",choices={"proteins":"proteins","precursors":"precursors"}),
                                      ui.output_plot("countscvcutoff")
                                    ),
                        #  ui.nav_panel("Unique Counts per Condition",
                        #               ui.output_plot("uniquecountsplot")
                        #             ),
                         ui.nav_panel("UpSet Plot",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("upsetplot_width","Plot width",min=500,max=2000,step=100,value=900,ticks=True),
                                              ui.input_slider("upsetplot_height","Plot height",min=500,max=2000,step=100,value=700,ticks=True)
                                            )
                                          ),
                                      ui.input_selectize("protein_precursor_pick","Pick which IDs to plot",choices={"Protein":"Protein","Peptide":"Peptide"}),
                                      ui.output_plot("upsetplot")
                                    )
                        ),icon=icon_svg("chart-simple")
                     ),
        ui.nav_panel("Metrics",
                     ui.navset_pill(
                         ui.nav_panel("Charge State",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("chargestate_width","Plot width",min=200,max=2000,step=100,value=1000,ticks=True),
                                              ui.input_slider("chargestate_height","Plot height",min=200,max=2000,step=100,value=500,ticks=True)
                                            )
                                          ),
                                      ui.output_plot("chargestateplot")
                                      ),
                         ui.nav_panel("Peptide Length",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("peptidelength_width","Plot width",min=200,max=2000,step=100,value=1000,ticks=True),
                                              ui.input_slider("peptidelength_height","Plot height",min=200,max=2000,step=100,value=500,ticks=True)
                                            )
                                          ),
                                      ui.input_selectize("peplengthinput","Line plot or bar plot?",choices={"lineplot":"line plot","barplot":"bar plot"}),
                                      ui.output_ui("lengthmark_ui"),
                                      ui.output_plot("peptidelengthplot")
                                      ),
                         ui.nav_panel("Peptides per Protein",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("pepsperprotein_width","Plot width",min=200,max=2000,step=100,value=1000,ticks=True),
                                              ui.input_slider("pepsperprotein_height","Plot height",min=200,max=2000,step=100,value=500,ticks=True)
                                            )
                                          ),
                                      ui.input_selectize("pepsperproteininput","Line plot or bar plot?",choices={"lineplot":"line plot","barplot":"bar plot"}),
                                      ui.output_plot("pepsperproteinplot")
                                      ),
                         ui.nav_panel("Dynamic Range",
                                      ui.output_ui("sampleconditions_ui"),
                                      ui.input_selectize("meanmedian","Mean or median",choices={"mean":"mean","median":"median"}),
                                      ui.output_plot("dynamicrangeplot")
                                      ),
                         ui.nav_panel("Data Completeness",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("datacompleteness_width","Plot width",min=200,max=2000,step=100,value=1000,ticks=True),
                                              ui.input_slider("datacompleteness_height","Plot height",min=200,max=2000,step=100,value=500,ticks=True)
                                            )
                                        ),
                                      ui.input_radio_buttons("protein_peptide","Pick what metric to plot:",choices={"proteins":"Proteins","peptides":"Peptides"}),
                                      ui.output_plot("datacompletenessplot")
                                      )
                        ),icon=icon_svg("chart-line")
                     ),
        ui.nav_panel("PTMs",
                     ui.navset_pill(
                         ui.nav_panel("PTMs found",
                             ui.output_ui("ptmlist_ui")
                             ),
                         ui.nav_panel("Counts per Condition",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("ptmidmetrics_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("ptmidmetrics_height","Plot height",min=500,max=2000,step=100,value=1000,ticks=True)
                                            )
                                          ),
                                      ui.input_selectize("ptmidplotinput","Choose what metric to plot:",choices={"all":"all","proteins":"proteins","proteins2pepts":"proteins2pepts","peptides":"peptides","precursors":"precursors"},multiple=False,selected="all"),
                                      ui.output_plot("ptmidmetricsplot")
                                      ),
                         ui.nav_panel("PTM Enrichment",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("ptmenrichment_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("ptmenrichment_height","Plot height",min=500,max=2000,step=100,value=1000,ticks=True)
                                            )
                                        ),
                                      ui.input_selectize("ptmenrichplotinput","Choose what metric to plot:",choices={"all":"all","proteins":"proteins","proteins2pepts":"proteins2pepts","peptides":"peptides","precursors":"precursors"},multiple=False,selected="all"),
                                      ui.output_plot("ptmenrichment")
                                      ),
                         ui.nav_panel("CV Plots",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("ptmcvplot_width","Plot width",min=500,max=2000,step=100,value=1000,ticks=True),
                                              ui.input_slider("ptmcvplot_height","Plot height",min=500,max=2000,step=100,value=500,ticks=True)
                                            )
                                        ),
                                      ui.row(
                                          ui.input_radio_buttons("ptm_proteins_precursors","Pick which IDs to plot",choices={"Protein":"Protein","Precursor":"Precursor"}),
                                          ui.input_switch("ptm_removetop5percent","Remove top 5%")
                                          ),
                                      ui.output_plot("ptm_cvplot")
                                      ),
                         ui.nav_panel("PTMs per Precursor",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("ptmsperprecursor_width","Plot width",min=500,max=2000,step=100,value=1000,ticks=True),
                                              ui.input_slider("ptmsperprecursor_height","Plot height",min=500,max=2000,step=100,value=600,ticks=True)
                                            )
                                          ),
                                      ui.input_slider("barwidth","Bar width",min=0.1,max=1,step=0.05,value=0.25,ticks=True),
                                      ui.output_plot("ptmsperprecursor")
                                      )
                            ),icon=icon_svg("binoculars")
                     ),
        ui.nav_panel("Heatmaps",
                     ui.navset_pill(
                        ui.nav_panel("RT, m/z, IM Heatmaps",
                                     ui.input_slider("heatmap_numbins","Number of bins",min=10,max=250,value=100,step=10,ticks=True),
                                     ui.input_selectize("conditiontype","Plot by individual replicate or by condition",choices={"replicate":"By replicate","condition":"By condition"}),
                                     ui.output_ui("cond_rep_list_heatmap"),
                                     ui.output_plot("replicate_heatmap")
                                     ),
                        ui.nav_panel("Charge/PTM Precursor Heatmap",
                                     ui.card(
                                         ui.input_file("diawindow_upload","Upload DIA windows as a .csv:")
                                         ),
                                     ui.row(
                                         ui.column(4,
                                                   ui.input_radio_buttons("windows_choice","Choose DIA windows to overlay:",choices={"imported":"Imported DIA windows","lubeck":"Lubeck DIA","phospho":"Phospho DIA","None":"None"},selected="None"),
                                                   ui.input_slider("chargeptm_numbins_x","Number of m/z bins",min=10,max=250,value=100,step=10,ticks=True),
                                                   ui.input_slider("chargeptm_numbins_y","Number of mobility bins",min=10,max=250,value=100,step=10,ticks=True),
                                                   ui.output_ui("chargestates_chargeptmheatmap_ui"),
                                                   ui.output_ui("ptm_chargeptmheatmap_ui"),
                                                   ),
                                         ui.column(6,
                                                   ui.output_plot("chargeptmheatmap")
                                                   )
                                             ),
                                     ),
                        ui.nav_panel("#IDs vs RT",
                                     ui.card(
                                         ui.row(
                                            ui.input_slider("idsvsrt_width","Plot width",min=500,max=2000,step=100,value=1000,ticks=True),
                                            ui.input_slider("idsvsrt_height","Plot height",min=300,max=2000,step=100,value=500,ticks=True)
                                            )
                                        ),
                                     ui.output_ui("binslider_ui"),
                                     ui.output_plot("ids_vs_rt")
                                     ),
                        ui.nav_panel("Venn Diagram of IDs",
                                     ui.output_ui("cond_rep_list_venn1"),
                                     ui.output_ui("cond_rep_list_venn2"),
                                     ui.input_selectize("vennpick","Pick what metric to compare:",choices={"proteins":"proteins","peptides":"peptides","precursors":"precursors"}),
                                     ui.output_plot("venndiagram")
                                     ),
                        ),icon=icon_svg("chart-area")
                     ),
        ui.nav_panel("Mixed Proteome",
                      ui.navset_pill(
                             ui.nav_panel("Info",
                                          ui.input_text("organisminput","Input organism names in all caps separated by a space (e.g. HUMAN YEAST ECOLI):"),
                                          ui.output_text_verbatim("organisminput_readout"),
                                          ui.input_radio_buttons("coloroptions_sumint","Use matplotlib tableau colors or blues/grays?",choices={"matplot":"matplotlib tableau","bluegray":"blues/grays"})
                                          ),
                             ui.nav_panel("Summed Intensities",
                                          ui.card(
                                              ui.row(
                                                  ui.input_slider("summedintensities_width","Plot width",min=500,max=2000,step=100,value=1000,ticks=True),
                                                  ui.input_slider("summedintensities_height","Plot height",min=500,max=2000,step=100,value=700,ticks=True)
                                              )
                                            ),
                                          ui.output_plot("summedintensities")
                                          ),
                             ui.nav_panel("Protein Counts per Organism",
                                          ui.card(
                                              ui.row(
                                                  ui.input_slider("countsperorganism_width","Plot width",min=500,max=2000,step=100,value=1000,ticks=True),
                                                  ui.input_slider("countsperorganism_height","Plot height",min=500,max=2000,step=100,value=700,ticks=True)
                                                )
                                            ),
                                          ui.output_plot("countsperorganism")
                                          ),
                             ui.nav_panel("Quant Ratios",
                                          ui.row(
                                              ui.column(4,
                                                        ui.output_ui("referencecondition"),ui.output_ui("testcondition"),ui.output_text_verbatim("organismreminder")
                                                        ),
                                              ui.column(4,
                                                        ui.input_text("referenceratio","Input ratios for each organism in the reference condition separated by a space: "),ui.output_text_verbatim("referenceratio_readout"),
                                                        ui.input_text("testratio","Input ratios for each organism in the test condition separated by a space: "),ui.output_text_verbatim("testratio_readout")
                                                        ),
                                              ui.column(3,
                                                        ui.input_slider("plotrange","Plot Range",min=-10,max=10,value=[-2,2],step=0.5,ticks=True,width="400px",drag_range=True),
                                                        ui.input_switch("plotrange_switch","Use slider for y-axis range"),
                                                        ui.input_slider("cvcutofflevel","CV Cutoff Level (%)",min=10,max=50,value=20,step=10,ticks=True,width="400px"),
                                                        ui.input_switch("cvcutoff_switch","Include CV cutoff?")),
                                                        ),
                                          ui.output_plot("quantratios")
                                          )
                            ),icon=icon_svg("flask")
                      ),
        ui.nav_panel("PRM",
                     ui.navset_pill(
                        ui.nav_panel("PRM List",
                                     ui.input_file("prm_list","Upload Peptide List:")
                                     ),
                        ui.nav_panel("PRM Table",
                                     ui.card(
                                         ui.row(
                                             ui.input_text("isolationwidth_input","m/z isolation width:"),
                                             ui.input_text("rtwindow_input","Retention time window (s):"),
                                             ui.input_text("imwindow_input","Ion mobility window (1/k0):")
                                             )
                                     ),
                                     ui.download_button("prm_table_download","Download PRM Table",width="300px",icon=icon_svg("file-arrow-down")),
                                     ui.output_data_frame("prm_table")
                                     ),
                        ui.nav_panel("PRM Peptides - Individual Tracker",
                                     ui.card(
                                        ui.row(
                                            ui.input_slider("prmpeptracker_width","Plot width",min=500,max=2000,step=100,value=1000,ticks=True),
                                            ui.input_slider("prmpeptracker_height","Plot height",min=500,max=2000,step=100,value=700,ticks=True)
                                        )
                                     ),
                                     ui.output_ui("prmpeptracker_pick"),
                                     ui.output_plot("prmpeptracker_plot")
                                     ),
                        ui.nav_panel("PRM Peptides - Intensity Across Runs",
                                     ui.card(
                                        ui.row(
                                            ui.input_slider("prmpepintensity_width","Plot width",min=500,max=2000,step=100,value=1000,ticks=True),
                                            ui.input_slider("prmpepintensity_height","Plot height",min=500,max=2000,step=100,value=700,ticks=True)
                                        )
                                     ),
                                     ui.output_plot("prmpepintensity_plot"),
                                     ),
                        # ui.nav_panel("Manual Peptide Tracker",
                        #              ui.row(
                        #                  ui.input_text("tracked_peptide","Input stripped peptide sequence:")
                        #                  ),
                        #                  ui.card(
                        #                      ui.output_plot("peptide_intensity")
                        #                      ),
                        #                  ui.card(
                        #                      ui.output_plot("peptide_replicates")
                        #                      )
                        #             )
                        ),icon=icon_svg("wand-sparkles")
                    ),
        # ui.nav_panel("Dilution Series",
        #              ui.navset_pill(
        #                  ui.nav_panel("")
        #              ),icon=icon_svg("vials")
        #             ),
        ui.nav_panel("Raw Data",
                     ui.navset_pill(
                         ui.nav_panel("Multi-File Import",
                                      ui.input_text_area("rawfile_input","Paste the path for each .d file you want to upload (note: do not leave whitespace at the end):",width="1500px",autoresize=True,placeholder="ex - C:\\Users\\Data\\K562_500ng_1_Slot1-49_1_3838.d")
                                      ),
                         ui.nav_panel("TIC Plot",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("tic_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("tic_height","Plot height",min=500,max=2000,step=100,value=600,ticks=True)
                                            )
                                          ),
                                      ui.card(
                                          ui.row(
                                              ui.output_ui("rawfile_checkboxes_tic")),
                                          ui.row(
                                              ui.input_switch("stacked_tic","Stack TIC Plots"))
                                          ),
                                      ui.output_plot("TIC_plot")
                                      ),
                         ui.nav_panel("BPC Plot",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("bpc_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("bpc_height","Plot height",min=500,max=2000,step=100,value=600,ticks=True)
                                            )
                                          ),
                                      ui.card(
                                          ui.row(
                                              ui.output_ui("rawfile_checkboxes_bpc")),
                                          ui.row(
                                              ui.input_switch("stacked_bpc","Stack BPC Plots"))
                                          ),
                                      ui.output_plot("BPC_plot")
                                      ),
                         ui.nav_panel("Accumulation Time",
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("accutime_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("accutime_height","Plot height",min=500,max=2000,step=100,value=600,ticks=True)
                                            )
                                          ),
                                      ui.card(
                                          ui.row(
                                              ui.output_ui("rawfile_checkboxes_accutime")),
                                          ui.row(
                                              ui.input_switch("stacked_accutime","Stack Plots"))
                                          ),
                                      ui.output_plot("accutime_plot")
                                      ),
                         ui.nav_panel("EIC Plot",
                                      ui.card(
                                          ui.row(ui.column(4,
                                                           ui.input_text("eic_mz_input","Input m/z for EIC:"),
                                                           ui.input_text("eic_ppm_input","Input mass error (ppm) for EIC:"),
                                                           ),
                                                 ui.column(4,
                                                           ui.input_switch("include_mobility","Include mobility in EIC"),
                                                           ui.output_ui("mobility_input")
                                                           ),
                                                ui.output_ui("rawfile_buttons")
                                            ),
                                          ui.input_action_button("load_eic","Load EIC",class_="btn-primary")
                                          ),
                                      ui.card(
                                          ui.row(
                                              ui.input_slider("eic_width","Plot width",min=500,max=2000,step=100,value=1500,ticks=True),
                                              ui.input_slider("eic_height","Plot height",min=200,max=2000,step=100,value=600,ticks=True)
                                            )
                                          ),
                                      ui.output_plot("eic")
                                      )
                         ),icon=icon_svg("desktop")
                     ),
        ui.nav_panel("Export Tables",
                     ui.navset_pill(
                         ui.nav_panel("Export Tables",
                                      ui.card(
                                          ui.card_header("Table of Peptide IDs"),
                                          ui.download_button("peptidelist","Download Peptide IDs",width="300px",icon=icon_svg("file-arrow-down")),
                                          ),
                                      ui.card(
                                          ui.card_header("Table of Protein ID Metrics and CVs"),
                                          ui.download_button("proteinidmetrics_download","Download Protein ID Metrics",width="300px",icon=icon_svg("file-arrow-down"))
                                          ),
                                      ui.card(
                                          ui.card_header("Table of Precursor ID Metrics and CVs"),
                                          ui.download_button("precursoridmetrics_download","Download Precursor ID Metrics",width="300px",icon=icon_svg("file-arrow-down"))
                                          ),
                                      ui.card(
                                          ui.card_header("List of MOMA Precursors"),
                                          ui.row(
                                              ui.column(4,
                                                        ui.output_ui("cond_rep_list"),
                                                        ui.download_button("moma_download","Download MOMA List",width="300px",icon=icon_svg("file-arrow-down"))
                                                        ),
                                              ui.column(4,
                                                        ui.input_slider("rttolerance","Retention time tolerance (%)",min=0.5,max=10,value=1,step=0.5,ticks=True),
                                                        ui.input_slider("mztolerance","m/z tolerance (m/z):",min=0.0005,max=0.1,value=0.005,step=0.0005,ticks=True)
                                              )
                                          )
                                          ),
                                      ui.card(
                                          ui.card_header("List of PTMs per Precursor"),
                                          ui.download_button("ptmlist_download","Download Precursor PTMs",width="300px",icon=icon_svg("file-arrow-down"))
                                          )
                                      )
                                ),icon=icon_svg("file-export")
                     ),
    widths=(3,8)
    ),
    theme=theme.cerulean()
)
#endregion

# =============================================================================
# Server
# =============================================================================

def server(input: Inputs, output: Outputs, session: Session):


# ============================================================================= UI calls
#region

    #render ui call for dropdown calling sample condition names
    @render.ui
    def sampleconditions_ui():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        opts=sampleconditions
        return ui.input_selectize("conditionname","Pick sample condition",choices=opts)

    #render ui call for dropdown calling replicate number
    @render.ui
    def replicates_ui():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        opts=np.arange(1,max(repspercondition)+1,1)
        return ui.input.selectize("replicate","Replicate number",opts)

    #render ui call for dropdown calling Cond_Rep column
    @render.ui
    def cond_rep_list():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        opts=resultdf["Cond_Rep"].tolist()
        return ui.input_selectize("cond_rep","Pick run:",choices=opts)    

#endregion

# ============================================================================= File Import, Metadata Generation, Updating searchoutput Based on Metadata
#region

    #import search report file
    @reactive.calc
    def inputfile():
        if input.searchreport() is None:
            return pd.DataFrame()
        searchoutput=pd.read_csv(input.searchreport()[0]["datapath"],sep="\t")
        if input.software()=="diann":
            searchoutput.rename(columns={"Run":"R.FileName"},inplace=True)
            searchoutput.insert(1,"R.Condition","")
            searchoutput.insert(2,"R.Replicate","")
        if input.software()=="ddalibrary":
            searchoutput.rename(columns={"ReferenceRun":"R.FileName"},inplace=True)
            searchoutput.insert(1,"R.Condition","")
            searchoutput.insert(2,"R.Replicate","")
        if input.software()=="timsdiann":
            searchoutput.rename(columns={"File.Name":"R.FileName"},inplace=True)
            searchoutput.insert(1,"R.Condition","")
            searchoutput.insert(2,"R.Replicate","")
        return searchoutput
    
    @render.data_frame
    def metadata_table():
        searchoutput=inputfile()
        if input.searchreport() is None:
            metadata=pd.DataFrame(columns=["R.FileName","R.Condition","R.Replicate","order","remove","Concentration"])
            return render.DataGrid(metadata,editable=True)
        metadata=pd.DataFrame(searchoutput[["R.FileName","R.Condition","R.Replicate"]]).drop_duplicates().reset_index(drop=True)
        metadata["order"]=metadata.apply(lambda _: '', axis=1)
        metadata["remove"]=metadata.apply(lambda _: '', axis=1)
        metadata["Concentration"]=metadata.apply(lambda _: '', axis=1)

        return render.DataGrid(metadata,editable=True,width="100%")

    #give a reminder for what to do with search reports from different software
    @render.text
    def metadata_reminder():
        if input.software()=="spectronaut":
            return "Spectronaut: Make sure to use Shiny report format when exporting search results"
        if input.software()=="diann":
            return "DIA-NN: Make sure to fill out R.Condition and R.Replicate columns in the metadata"
        if input.software()=="ddalibrary":
            return "DDA Library: DDA libraries have limited functionality, can only plot ID metrics"
        if input.software()=="timsdiann":
            return "BPS tims-DIANN: to access results file, unzip the bps_timsDIANN folder, open the processing-run folder and its subfolder, then unzip the tims-diann.result folder. Upload the results.tsv and then make sure to fill out R.Condition and R.Replicate columns in the metadata"

    #update the searchoutput df to match how we edited the metadata sheet
    @reactive.calc
    @reactive.event(input.rerun_metadata,ignore_none=False)
    def metadata_update():
        searchoutput=inputfile()
        #metadata=metadatafile()
        metadata=metadata_table.data_view()
        #remove/resort conditions but do not change condition names
        if input.condition_names()==False and input.concentration()==False and input.remove_resort()==True:
            sortedmetadata=metadata[metadata.remove !="x"].sort_values(by="order").reset_index(drop=True)
            searchoutput=searchoutput.set_index("R.FileName").loc[sortedmetadata["R.FileName"].tolist()].reset_index()

        elif input.condition_names()==False and input.concentration()==True and input.remove_resort()==False:
            concentrationlist=[]
            for i in searchoutput["R.FileName"]:
                fileindex=metadata[metadata["R.FileName"]==i].index.values[0]
                concentrationlist.append(float(metadata["Concentration"][fileindex]))
            if "Concentration" in searchoutput.columns:
                searchoutput["Concentration"]=concentrationlist
            else:
                searchoutput.insert(3,"Concentration",concentrationlist)

        #change condition names but do not remove or resort
        elif input.condition_names()==True and input.concentration()==False and input.remove_resort()==False:
            concentrationlist=[]
            RConditionlist=[]
            RReplicatelist=[]
            for i in searchoutput["R.FileName"]:
                fileindex=metadata[metadata["R.FileName"]==i].index.values[0]
                RConditionlist.append(metadata["R.Condition"][fileindex])
                RReplicatelist.append(int(metadata["R.Replicate"][fileindex]))
            searchoutput["R.Condition"]=RConditionlist
            searchoutput["R.Replicate"]=RReplicatelist
 
        #remove/resort conditions and change condition names
        elif input.condition_names()==True and input.concentration()==True and input.remove_resort()==True:
            sortedmetadata=metadata[metadata.remove !="x"].sort_values(by="order").reset_index(drop=True)
            searchoutput=searchoutput.set_index("R.FileName").loc[sortedmetadata["R.FileName"].tolist()].reset_index()

            concentrationlist=[]
            RConditionlist=[]
            RReplicatelist=[]
            for i in searchoutput["R.FileName"]:
                fileindex=metadata[metadata["R.FileName"]==i].index.values[0]
                concentrationlist.append(float(metadata["Concentration"][fileindex]))
                RConditionlist.append(metadata["R.Condition"][fileindex])
                RReplicatelist.append(int(metadata["R.Replicate"][fileindex]))
            searchoutput["R.Condition"]=RConditionlist
            searchoutput["R.Replicate"]=RReplicatelist
            if "Concentration" in searchoutput.columns:
                searchoutput["Concentration"]=concentrationlist
            else:
                searchoutput.insert(3,"Concentration",concentrationlist)

        #adjusting the searchoutput sheet depending on the search software
        if input.software()=="diann":
            searchoutput["EG.PeakWidth"]=searchoutput["RT.Stop"]-searchoutput["RT.Start"]
            searchoutput.drop(columns=["File.Name","PG.Normalized","PG.MaxLFQ","Genes.Quantity",
                                        "Genes.Normalised","Genes.MaxLFQ","Genes.MaxLFQ.Unique","Precursor.Id",
                                        "PEP","Global.Q.Value","Protein.Q.Value","Global.PG.Q.Value","GG.Q.Value",
                                        "Translated.Q.Value","Precursor.Translated","Translated.Quality",
                                        "Ms1.Translated","Quantity.Quality","RT.Stop","RT.Start","iRT","Predicted.iRT",
                                        "First.Protein.Description","Lib.Q.Value","Lib.PG.Q.Value","Ms1.Profile.Corr",
                                        "Ms1.Area","Evidence","Spectrum.Similarity","Averagine","Mass.Evidence",
                                        "Decoy.Evidence","Decoy.CScore","Fragment.Quant.Raw","Fragment.Quant.Corrected",
                                        "Fragment.Correlations","MS2.Scan","iIM","Predicted.IM",
                                        "Predicted.iIM"],inplace=True)
            searchoutput.rename(columns={#"Run":"R.FileName",
                        "Protein.Group":"PG.ProteinGroups",
                        "Protein.Ids":"PG.ProteinAccessions",
                        "Protein.Names":"PG.ProteinNames",
                        "PG.Quantity":"PG.MS2Quantity",
                        "Genes":"PG.Genes",
                        "Stripped.Sequence":"PEP.StrippedSequence",
                        "Modified.Sequence":"EG.ModifiedPeptide",
                        "Precursor.Charge":"FG.Charge",
                        "Q.Value":"EG.Qvalue",
                        "PG.Q.Value":"PG.Qvalue",
                        "Precursor.Quantity":"FG.MS2Quantity",
                        "Precursor.Normalised":"FG.MS2RawQuantity",
                        "RT":"EG.ApexRT",
                        "Predicted.RT":"EG.RTPredicted",
                        "CScore":"EG.Cscore",
                        "IM":"EG.IonMobility",
                        "Proteotypic":"PEP.IsProteotypic"},inplace=True)
            searchoutput["EG.ModifiedPeptide"]=searchoutput["EG.ModifiedPeptide"].str.replace("(","[")
            searchoutput["EG.ModifiedPeptide"]=searchoutput["EG.ModifiedPeptide"].str.replace(")","]")
            searchoutput["EG.ModifiedPeptide"]=searchoutput["EG.ModifiedPeptide"].replace({
                    "UniMod:1":"Acetyl (Protein N-term)",
                    "UniMod:4":"Carbamidomethyl (C)",
                    "UniMod:21":"Phospho (STY)",
                    "UniMod:35":"Oxidation (M)"},regex=True)
        if input.software()=="ddalibrary":
            searchoutput=searchoutput.rename(columns={"ReferenceRun":"R.FileName",
                            "PrecursorCharge":"FG.Charge",
                            "ModifiedPeptide":"EG.ModifiedPeptide",
                            "StrippedPeptide":"PEP.StrippedSequence",
                            "IonMobility":"EG.IonMobility",
                            "PrecursorMz":"FG.PrecMz",
                            "ReferenceRunMS1Response":"FG.MS2Quantity",
                            "Protein Name":"PG.ProteinNames"})
            searchoutput.insert(1,"R.Condition","")
            searchoutput.insert(2,"R.Replicate","")
        if input.software()=="timsdiann":
            searchoutput["EG.PeakWidth"]=searchoutput["RT.Stop"]-searchoutput["RT.Start"]
            searchoutput.drop(columns=["Run","PG.Normalised","Genes.Quantity",
                                       "Genes.Normalised","Genes.MaxLFQ","Genes.MaxLFQ.Unique","PG.MaxLFQ",
                                       "Precursor.Id","Protein.Q.Value","GG.Q.Value","Label.Ratio",
                                       "Quantity.Quality","RT.Start","RT.Stop","iRT","Predicted.iRT",
                                       "First.Protein.Description","Lib.Q.Value","Ms1.Profile.Corr",
                                       "Ms1.Corr.Sum","Ms1.Area","Evidence","Decoy.Evidence","Decoy.CScore",
                                       "Fragment.Quant.Raw","Fragment.Quant.Corrected","Fragment.Correlations",
                                       "MS2.Scan","Precursor.FWHM","Precursor.Error.Ppm","Corr.Precursor.Error.Ppm",
                                       "Data.Points","Ms1.Iso.Corr.Sum","Library.Precursor.Mz","Corrected.Precursor.Mz",
                                       "Precursor.Calibrated.Mz","Fragment.Info","Fragment.Calibrated.Mz","Lib.1/K0"],inplace=True)

            searchoutput.rename(columns={"Protein.Group":"PG.ProteinGroups",
                                         "Protein.Ids":"PG.ProteinAccessions",
                                         "Protein.Names":"PG.ProteinNames",
                                         "Genes":"PG.Genes",
                                         "PG.Quantity":"PG.MS2Quantity",
                                         "Modified.Sequence":"EG.ModifiedPeptide",
                                         "Stripped.Sequence":"PEP.StrippedSequence",
                                         "Precursor.Charge":"FG.Charge",
                                         "Q.Value":"EG.Qvalue",
                                         "PG.Q.Value":"PG.Qvalue",
                                         "Precursor.Quantity":"FG.MS2Quantity",
                                         "Precursor.Normalized":"FG.MS2RawQuantity",
                                         "RT":"EG.ApexRT",
                                         "Predicted.RT":"EG.RTPredicted",
                                         "CScore":"EG.CScore",
                                         "Proteotypic":"PEP.IsProteotypic",
                                         "Exp.1/K0":"EG.IonMobility"},inplace=True)

            searchoutput["EG.ModifiedPeptide"]=searchoutput["EG.ModifiedPeptide"].str.replace("(UniMod:7)","")
            searchoutput["EG.ModifiedPeptide"]=searchoutput["EG.ModifiedPeptide"].str.replace("(","[")
            searchoutput["EG.ModifiedPeptide"]=searchoutput["EG.ModifiedPeptide"].str.replace(")","]")

            searchoutput["EG.ModifiedPeptide"]=searchoutput["EG.ModifiedPeptide"].replace({
                    "UniMod:1":"Acetyl (Protein N-term)",
                    "UniMod:4":"Carbamidomethyl (C)",
                    "UniMod:21":"Phospho (STY)",
                    "UniMod:35":"Oxidation (M)"},regex=True)            
        
        return searchoutput

#endregion

# ============================================================================= Generate Necessary Variables and Dataframes, Calculate ID Metrics, Generate Colormaps for Plotting
#region

    #searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
    #resultdf,averagedf=idmetrics()

    #take searchoutput df and generate variables and dataframes to be used downstream
    @reactive.calc
    def variables_dfs():
        searchoutput=metadata_update()
        searchoutput["R.Condition"]=searchoutput["R.Condition"].apply(str)
        if "Cond_Rep" not in searchoutput.columns:
            searchoutput.insert(0,"Cond_Rep",searchoutput["R.Condition"]+"_"+searchoutput["R.Replicate"].apply(str))
        elif "Cond_Rep" in searchoutput.columns:
            if input.condition_names()==True:
                searchoutput["Cond_Rep"]=searchoutput["R.Condition"]+"_"+searchoutput["R.Replicate"].apply(str)
        resultdf=pd.DataFrame(searchoutput[["Cond_Rep","R.FileName","R.Condition","R.Replicate"]].drop_duplicates()).reset_index(drop=True)
        sampleconditions=searchoutput["R.Condition"].drop_duplicates().tolist()
        maxreplicatelist=[]
        for i in sampleconditions:
            samplegroup=pd.DataFrame(searchoutput[searchoutput["R.Condition"].str.contains(i)])
            maxreplicates=max(samplegroup["R.Replicate"].tolist())
            maxreplicatelist.append(maxreplicates)
        averagedf=pd.DataFrame({"R.Condition":sampleconditions,"N.Replicates":maxreplicatelist})
        numconditions=len(averagedf["R.Condition"].tolist())
        repspercondition=averagedf["N.Replicates"].tolist()
        numsamples=len(resultdf["R.Condition"].tolist())

        return searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples

    #use the variables_dfs function that imports the searchoutput df to generate colormaps for plotting
    @reactive.calc
    def colordfs():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        samplelinspace=np.linspace(0,1,numconditions)
        colorarray=[]
        for i in range(numconditions):
            x=repspercondition[i]
            for ele in range(x):
                colorarray.append(samplelinspace[i])
        rainbowlist=cm.gist_rainbow(colorarray)
        colorblocks=[]
        for i in range(len(rainbowlist)):
            colorblocks.append(sns.desaturate(rainbowlist[i],0.75))

        n=numsamples
        color=cm.gist_rainbow(np.linspace(0,1,n))
        colors=[]
        for i in range(len(color)):
            colors.append(sns.desaturate(color[i],0.75))
            
        matplottabcolors=list(mcolors.TABLEAU_COLORS)

        tabcolorsblocks=[]
        if numconditions > len(matplottabcolors):
            dif=numconditions-len(matplottabcolors)
            for i in range(dif):
                tabcolorsblocks.append(matplottabcolors[i])    
            for i in range(numconditions):      
                x=repspercondition[i]
                for ele in range(x):
                    tabcolorsblocks.append(matplottabcolors[i])
        else:
            for i in range(numconditions):      
                x=repspercondition[i]
                for ele in range(x):
                    tabcolorsblocks.append(matplottabcolors[i])

        return colorblocks,colors,matplottabcolors,tabcolorsblocks
    
    #use the variables_dfs function that imports the searchoutput df to calculate ID metrics
    #most updated calcs for resultdf and averagedf
    @reactive.calc
    def idmetrics():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        numproteins=[]
        numproteins2pepts=[]
        numpeptides=[]
        numprecursors=[]
        for i in sampleconditions:
            for j in range(max(maxreplicatelist)+1):
                replicatedata=searchoutput[searchoutput["R.Condition"].str.contains(i)&(searchoutput["R.Replicate"]==j)]
                if replicatedata.empty:
                    continue
                #identified proteins
                numproteins.append(replicatedata["PG.ProteinNames"].nunique())
                #identified proteins with 2 peptides
                numproteins2pepts.append(len(replicatedata[["PG.ProteinNames","EG.ModifiedPeptide"]].drop_duplicates().groupby("PG.ProteinNames").size().reset_index(name="peptides").query("peptides>1")))
                #identified peptides
                numpeptides.append(replicatedata["EG.ModifiedPeptide"].nunique())
                #identified precursors
                numprecursors.append(len(replicatedata[["EG.ModifiedPeptide","FG.Charge"]]))
        resultdf["proteins"]=numproteins
        resultdf["proteins2pepts"]=numproteins2pepts
        resultdf["peptides"]=numpeptides
        resultdf["precursors"]=numprecursors
        
        #avg and stdev values for IDs appended to averagedf dataframe, which holds lists of all the calculated values here
        columnlist=resultdf.columns.values.tolist()
        for i in columnlist:
            if i=="R.FileName" or i=="Cond_Rep" or i=="R.Condition" or i=="R.Replicate":
                continue
            avglist=[]
            stdevlist=[]
            for j in sampleconditions:
                samplecondition=resultdf[resultdf["R.Condition"].str.contains(j)]
                avglist.append(round(np.average(samplecondition[i].to_numpy())))
                stdevlist.append(np.std(samplecondition[i].to_numpy()))
            averagedf[i+"_avg"]=avglist
            averagedf[i+"_stdev"]=stdevlist

        #charge states
        chargestatelist=[]
        chargestategroup=searchoutput[["R.Condition","PEP.StrippedSequence","FG.Charge"]].drop_duplicates().reset_index(drop=True)
        for condition in averagedf["R.Condition"]:
            df=pd.DataFrame(chargestategroup[chargestategroup["R.Condition"].str.contains(condition)].drop(columns=["R.Condition","PEP.StrippedSequence"]))
            chargestatelist.append(df["FG.Charge"].tolist())
        averagedf["Charge States"]=chargestatelist

        #peptide lengths
        listoflengths=[]
        for i in averagedf["R.Condition"]:
            placeholder=searchoutput[searchoutput["R.Condition"].str.contains(i)]["PEP.StrippedSequence"].drop_duplicates().reset_index(drop=True).tolist()
            lengths=[]
            for pep in placeholder:
                lengths.append(len(pep))
            listoflengths.append(lengths)
        averagedf["Peptide Lengths"]=listoflengths

        #number of peptides per protein
        pepsperproteinlist=[]
        for condition in averagedf["R.Condition"]:
            df=searchoutput[searchoutput["R.Condition"].str.contains(condition)][["R.Condition","PG.ProteinNames","EG.ModifiedPeptide"]].drop_duplicates().drop(columns="R.Condition").reset_index(drop=True)
            pepsperproteinlist.append(df.groupby(["PG.ProteinNames"]).size().tolist())
        averagedf["Peptides per Protein"]=pepsperproteinlist

        #protein-level CVs
        proteincvlist=[]
        proteincvlist95=[]
        proteincvdict={}
        cvproteingroup=searchoutput[
            ["R.Condition","R.Replicate","PG.ProteinGroups","PG.MS2Quantity"]
            ].drop_duplicates().reset_index(drop=True)
        for x,condition in enumerate(sampleconditions):
            if maxreplicatelist[x]==1:
                emptylist=[]
                proteincvlist.append(emptylist)
                proteincvlist95.append(emptylist)
            else:
                df=pd.DataFrame(cvproteingroup[cvproteingroup["R.Condition"].str.contains(condition)]).drop(columns=["R.Condition","R.Replicate"])
                mean=df.groupby("PG.ProteinGroups").mean().rename(columns={"PG.MS2Quantity":"Protein Mean"})
                std=df.groupby("PG.ProteinGroups").std().rename(columns={"PG.MS2Quantity":"Protein Std"})
                cvproteintable=pd.concat([mean,std],axis=1)
                cvproteintable.dropna(inplace=True)
                cvlist=(cvproteintable["Protein Std"]/cvproteintable["Protein Mean"]*100).tolist()
                proteincvdict[condition]=pd.DataFrame(cvlist,columns=["CV"])
                proteincvlist.append(cvlist)
                top95=np.percentile(cvlist,95)
                cvlist95=[]
                for i in cvlist:
                    if i <=top95:
                        cvlist95.append(i)
                proteincvlist95.append(cvlist95)
        averagedf["Protein CVs"]=proteincvlist
        averagedf["Protein 95% CVs"]=proteincvlist95

        #precursor-level CVs
        precursorcvlist=[]
        precursorcvlist95=[]
        precursorcvdict={}
        cvprecursorgroup=searchoutput[
            ["R.Condition","R.Replicate","EG.ModifiedPeptide","FG.Charge","FG.MS2Quantity"]
            ].drop_duplicates().reset_index(drop=True)
        for x,condition in enumerate(sampleconditions):
            if maxreplicatelist[x]==1:
                emptylist=[]
                precursorcvlist.append(emptylist)
                precursorcvlist95.append(emptylist)
            else:
                df=pd.DataFrame(cvprecursorgroup[cvprecursorgroup["R.Condition"].str.contains(condition)]).drop(columns=["R.Condition","R.Replicate"])
                mean=df.groupby(["EG.ModifiedPeptide","FG.Charge"]).mean().rename(columns={"FG.MS2Quantity":"Precursor Mean"})
                std=df.groupby(["EG.ModifiedPeptide","FG.Charge"]).std().rename(columns={"FG.MS2Quantity":"Precursor Std"})
                cvprecursortable=pd.concat([mean,std],axis=1)
                cvprecursortable.dropna(inplace=True)
                cvlist=(cvprecursortable["Precursor Std"]/cvprecursortable["Precursor Mean"]*100).tolist()
                precursorcvdict[condition]=pd.DataFrame(cvlist,columns=["CV"])
                precursorcvlist.append(cvlist)
                top95=np.percentile(cvlist,95)
                cvlist95=[]
                for i in cvlist:
                    if i <=top95:
                        cvlist95.append(i)
                precursorcvlist95.append(cvlist95)
        averagedf["Precursor CVs"]=precursorcvlist
        averagedf["Precursor 95% CVs"]=precursorcvlist95

        #counts above CV cutoffs
        #protein CVs
        proteinscv20=[]
        proteinscv10=[]
        for x,condition in enumerate(sampleconditions):
            if maxreplicatelist[x]==1:
                emptylist=[]
                proteinscv20.append(emptylist)
                proteinscv10.append(emptylist)
            else:
                proteinscv20.append(proteincvdict[condition][proteincvdict[condition]["CV"]<20].shape[0])
                proteinscv10.append(proteincvdict[condition][proteincvdict[condition]["CV"]<10].shape[0])

        averagedf["proteinsCV<20"]=proteinscv20
        averagedf["proteinsCV<10"]=proteinscv10

        #precursor CVs
        precursorscv20=[]
        precursorscv10=[]
        for x,condition in enumerate(sampleconditions):
            if maxreplicatelist[x]==1:
                emptylist=[]
                precursorscv20.append(emptylist)
                precursorscv10.append(emptylist)
            else:
                precursorscv20.append(precursorcvdict[condition][precursorcvdict[condition]["CV"]<20].shape[0])
                precursorscv10.append(precursorcvdict[condition][precursorcvdict[condition]["CV"]<10].shape[0])
        averagedf["precursorsCV<20"]=precursorscv20
        averagedf["precursorsCV<10"]=precursorscv10

        return resultdf,averagedf

#endregion

# ============================================================================= Color Options
#region

    #function for showing color options
    def plot_colortable(colors, *, ncols=4, sort_colors=True):
        #from https://matplotlib.org/stable/gallery/color/named_colors.html

        cell_width = 212
        cell_height = 22
        swatch_width = 48
        margin = 12

        # Sort colors by hue, saturation, value and name.
        if sort_colors is True:
            names = sorted(
                colors, key=lambda c: tuple(mcolors.rgb_to_hsv(mcolors.to_rgb(c))))
        else:
            names = list(colors)

        n = len(names)
        nrows = math.ceil(n / ncols)

        width = cell_width * ncols + 2 * margin
        height = cell_height * nrows + 2 * margin
        dpi = 72

        fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
        fig.subplots_adjust(margin/width, margin/height,
                            (width-margin)/width, (height-margin)/height)
        ax.set_xlim(0, cell_width * ncols)
        ax.set_ylim(cell_height * (nrows-0.5), -cell_height/2.)
        ax.yaxis.set_visible(False)
        ax.xaxis.set_visible(False)
        ax.set_axis_off()

        for i, name in enumerate(names):
            row = i % nrows
            col = i // nrows
            y = row * cell_height

            swatch_start_x = cell_width * col
            text_pos_x = cell_width * col + swatch_width + 7

            ax.text(text_pos_x, y, name, fontsize=14,
                    horizontalalignment='left',
                    verticalalignment='center')

            ax.add_patch(
                Rectangle(xy=(swatch_start_x, y-9), width=swatch_width,
                        height=18, facecolor=colors[name], edgecolor='0.7')
            )

        return fig

    @render.plot(width=200,height=500)
    def matplotlibcolors():
        return plot_colortable(mcolors.TABLEAU_COLORS, ncols=1, sort_colors=False)
    
    @render.plot(width=800,height=800)
    def csscolors():
        return plot_colortable(mcolors.CSS4_COLORS)

    @render.text
    def matplotlibcolors_text():
        return ("Matplotlib Tableau Colors:")
    @render.text
    def csscolors_text():
        return ("CSS Colors:")

    @reactive.calc
    def colorpicker():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        if input.coloroptions()=="pickrainbow":
            if numconditions==2:
                rainbowlist=cm.gist_rainbow(np.linspace(0,1,6))
                plotcolors=[]
                for i in range(len(rainbowlist)):
                    plotcolors.append(sns.desaturate(rainbowlist[i],0.75))
                indices=[0,3]
                plotcolors=[plotcolors[x] for x in indices]
            elif numconditions==1:
                plotcolors=sns.desaturate(cm.gist_rainbow(np.random.random_sample()),0.75)
            else:
                samplelinspace=np.linspace(0,1,numconditions)
                rainbowlist=cm.gist_rainbow(samplelinspace)
                plotcolors=[]
                for i in range(len(rainbowlist)):
                    plotcolors.append(sns.desaturate(rainbowlist[i],0.75))
        elif input.coloroptions()=="pickmatplot":
            matplottabcolors=list(mcolors.TABLEAU_COLORS)
            plotcolors=[]
            if numconditions > len(matplottabcolors):
                dif=numconditions-len(matplottabcolors)
                for i in range(dif):
                    plotcolors.append(matplottabcolors[i])
            elif numconditions==1:
                plotcolors=matplottabcolors[np.random.randint(low=0,high=len(list(mcolors.TABLEAU_COLORS)))]
            else:
                for i in range(numconditions):
                    plotcolors.append(matplottabcolors[i])
        elif input.coloroptions()=="custom":
            if numconditions==1:
                plotcolors=input.customcolors()
            else:
                plotcolors=list(input.customcolors().split("\n"))
        return plotcolors
    
    @reactive.calc
    #loop to extend list for replicates
    def replicatecolors():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        plotcolors=colorpicker()
        if numconditions==1 and len(maxreplicatelist)==1:
            return plotcolors
        else:
            replicateplotcolors=[]
            for i in range(numconditions):
                x=repspercondition[i]
                for ele in range(x):
                    replicateplotcolors.append(plotcolors[i])
            return replicateplotcolors

    @render.text
    def colornote():
        return "Note: replicates of the same condition will have the same color"
    @render.table()
    def customcolors_table1():
        try:
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            conditioncolordf1=pd.DataFrame({"Run":sampleconditions})
            return conditioncolordf1
        except:
            conditioncolordf1=pd.DataFrame({"Run":[]})
            return conditioncolordf1

    @render.table
    def conditioncolors():
        conditioncolors_table=pd.DataFrame({"Color per run":[]})
        return conditioncolors_table
    @render.plot(width=75,height=125)
    def customcolors_plot():
        try:
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            plotcolors=colorpicker()
            
            fig,ax=plt.subplots(nrows=len(sampleconditions))
            fig.set_tight_layout(True)
            for i in range(len(sampleconditions)):
                if len(sampleconditions)==1:
                    rect=matplotlib.patches.Rectangle(xy=(0,0),width=0.5,height=0.5,facecolor=plotcolors)
                    ax.add_patch(rect)
                    ax.axis("off")
                    ax.set_ylim(bottom=0,top=0.5)
                    ax.set_xlim(left=0,right=0.5)
                else:
                    rect=matplotlib.patches.Rectangle(xy=(0,0),width=0.5,height=0.5,facecolor=plotcolors[i])
                    ax[i].add_patch(rect)
                    ax[i].axis("off")
                    ax[i].set_ylim(bottom=0,top=0.5)
                    ax[i].set_xlim(left=0,right=0.5)
        except:
            pass

#endregion   

# ============================================================================= ID Counts
#region

    #plot ID metrics
    @reactive.effect()
    def _():
        if input.idplotinput()=="all":
            @render.plot(width=input.idmetrics_width(),height=input.idmetrics_height())
            def idmetricsplot():
                resultdf,averagedf=idmetrics()
                idmetricscolor=replicatecolors()
                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.4

                fig,ax=plt.subplots(nrows=2,ncols=2,figsize=figsize,sharex=True)
                fig.set_tight_layout(True)
                ax1=ax[0,0]
                ax2=ax[0,1]
                ax3=ax[1,0]
                ax4=ax[1,1]

                resultdf.plot.bar(ax=ax1,x="Cond_Rep",y="proteins",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax1.bar_label(ax1.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax1.set_ylim(top=max(resultdf["proteins"].tolist())+y_padding*max(resultdf["proteins"].tolist()))
                ax1.set_title("Proteins",fontsize=titlefont)

                resultdf.plot.bar(ax=ax2,x="Cond_Rep",y="proteins2pepts",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax2.bar_label(ax2.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax2.set_ylim(top=max(resultdf["proteins2pepts"].tolist())+y_padding*max(resultdf["proteins2pepts"].tolist()))
                ax2.set_title("Proteins2Pepts",fontsize=titlefont)

                resultdf.plot.bar(ax=ax3,x="Cond_Rep",y="peptides",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax3.bar_label(ax3.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax3.set_ylim(top=max(resultdf["peptides"].tolist())+(y_padding+0.1)*max(resultdf["peptides"].tolist()))
                ax3.set_title("Peptides",fontsize=titlefont)
                ax3.set_xlabel("Condition",fontsize=titlefont)
                ax3.set_ylabel("  ",fontsize=titlefont)

                resultdf.plot.bar(ax=ax4,x="Cond_Rep",y="precursors",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax4.bar_label(ax4.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax4.set_ylim(top=max(resultdf["precursors"].tolist())+(y_padding+0.1)*max(resultdf["precursors"].tolist()))
                ax4.set_title("Precursors",fontsize=titlefont)
                ax4.set_xlabel("Condition",fontsize=titlefont)

                fig.text(0, 0.6,"Counts",ha="left",va="center",rotation="vertical",fontsize=titlefont)

                ax1.set_axisbelow(True)
                ax1.grid(linestyle="--")
                ax2.set_axisbelow(True)
                ax2.grid(linestyle="--")
                ax3.set_axisbelow(True)
                ax3.grid(linestyle="--")
                ax4.set_axisbelow(True)
                ax4.grid(linestyle="--")
        else:
            @render.plot(width=input.idmetrics_width(),height=input.idmetrics_height())
            def idmetricsplot():
                resultdf,averagedf=idmetrics()
                idmetricscolor=replicatecolors()
                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.4

                fig,ax=plt.subplots()
                plotinput=input.idplotinput()
                resultdf.plot.bar(ax=ax,x="Cond_Rep",y=plotinput,legend=False,width=0.8,color=idmetricscolor,edgecolor="k")
                ax.bar_label(ax.containers[0],label_type="edge",rotation=90,padding=5,fontsize=axisfont)
                ax.set_ylim(top=max(resultdf[plotinput].tolist())+y_padding*max(resultdf[plotinput].tolist()))
                ax.set_ylabel("Counts",fontsize=titlefont)
                ax.set_xlabel("Condition",fontsize=titlefont)
                ax.set_title(plotinput,fontsize=titlefont)
                ax.tick_params(axis="both",labelsize=axisfont)
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
    
    #plot average ID metrics
    @reactive.effect
    def _():
        if input.avgidplotinput()=="all":
            @render.plot(width=input.avgidmetrics_width(),height=input.avgidmetrics_height())
            def avgidmetricsplot():
                resultdf,averagedf=idmetrics()
                #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()
                #avgmetricscolor=matplottabcolors
                avgmetricscolor=colorpicker()

                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.3

                fig,ax=plt.subplots(nrows=2,ncols=2,figsize=figsize)
                fig.set_tight_layout(True)
                ax1=ax[0,0]
                ax2=ax[0,1]
                ax3=ax[1,0]
                ax4=ax[1,1]

                bars1=ax1.bar(averagedf["R.Condition"],averagedf["proteins_avg"],yerr=averagedf["proteins_stdev"],edgecolor="k",capsize=10,color=avgmetricscolor)
                ax1.bar_label(bars1,label_type="edge",rotation=90,padding=10,fontsize=labelfont)
                ax1.set_ylim(top=max(averagedf["proteins_avg"].tolist())+y_padding*max(averagedf["proteins_avg"].tolist()))
                ax1.set_title("Proteins",fontsize=titlefont)
                ax1.tick_params(axis='y',labelsize=axisfont)
                ax1.tick_params(axis='x',labelbottom=False)

                bars2=ax2.bar(averagedf["R.Condition"],averagedf["proteins2pepts_avg"],yerr=averagedf["proteins2pepts_stdev"],edgecolor="k",capsize=10,color=avgmetricscolor)
                ax2.bar_label(bars2,label_type="edge",rotation=90,padding=10,fontsize=labelfont)
                ax2.set_ylim(top=max(averagedf["proteins2pepts_avg"].tolist())+y_padding*max(averagedf["proteins2pepts_avg"].tolist()))
                ax2.set_title("Proteins2pepts",fontsize=titlefont)
                ax2.tick_params(axis='y',labelsize=axisfont)
                ax2.tick_params(axis='x',labelbottom=False)

                bars3=ax3.bar(averagedf["R.Condition"],averagedf["peptides_avg"],yerr=averagedf["peptides_stdev"],edgecolor="k",capsize=10,color=avgmetricscolor)
                ax3.bar_label(bars3,label_type="edge",rotation=90,padding=10,fontsize=labelfont)
                ax3.set_ylim(top=max(averagedf["peptides_avg"].tolist())+y_padding*max(averagedf["peptides_avg"].tolist()))
                ax3.set_title("Peptides",fontsize=titlefont)
                ax3.tick_params(axis='y',labelsize=axisfont)
                ax3.tick_params(axis='x',labelsize=axisfont,rotation=90)
                ax3.set_xlabel("Condition",fontsize=titlefont)
                ax3.set_ylabel("  ",fontsize=titlefont)

                bars4=ax4.bar(averagedf["R.Condition"],averagedf["precursors_avg"],yerr=averagedf["precursors_stdev"],edgecolor="k",capsize=10,color=avgmetricscolor)
                ax4.bar_label(bars4,label_type="edge",rotation=90,padding=10,fontsize=labelfont)
                ax4.set_ylim(top=max(averagedf["precursors_avg"].tolist())+y_padding*max(averagedf["precursors_avg"].tolist()))
                ax4.set_title("Precursors",fontsize=titlefont)
                ax4.tick_params(axis='y',labelsize=axisfont)
                ax4.tick_params(axis='x',labelsize=axisfont,rotation=90)
                ax4.set_xlabel("Condition",fontsize=titlefont)

                fig.text(0, 0.6,"Counts",ha="left",va="center",rotation="vertical",fontsize=titlefont)

                ax1.set_axisbelow(True)
                ax1.grid(linestyle="--")
                ax2.set_axisbelow(True)
                ax2.grid(linestyle="--")
                ax3.set_axisbelow(True)
                ax3.grid(linestyle="--")
                ax4.set_axisbelow(True)
                ax4.grid(linestyle="--")
            
        else:
            @render.plot(width=input.avgidmetrics_width(),height=input.avgidmetrics_height())
            def avgidmetricsplot():
                resultdf,averagedf=idmetrics()
                avgmetricscolor=colorpicker()

                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.3
                fig,ax=plt.subplots()
                avgplotinput=input.avgidplotinput()
                bars=ax.bar(averagedf["R.Condition"],averagedf[avgplotinput+"_avg"],yerr=averagedf[avgplotinput+"_stdev"],edgecolor="k",capsize=10,color=avgmetricscolor)
                ax.bar_label(bars,label_type="edge",rotation=90,padding=10,fontsize=labelfont)
                ax.set_ylim(top=max(averagedf[avgplotinput+"_avg"].tolist())+y_padding*max(averagedf[avgplotinput+"_avg"].tolist()))
                plt.ylabel("Counts",fontsize=axisfont)
                plt.xlabel("Condition",fontsize=axisfont)
                plt.title("Average #"+avgplotinput,fontsize=titlefont)
                ax.tick_params(axis="both",labelsize=axisfont)
                ax.tick_params(axis='x',labelsize=axisfont,rotation=90)
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")

    #plot cv violin plots
    @reactive.effect
    def _():
        @render.plot(width=input.cvplot_width(),height=input.cvplot_height())
        def cvplot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()
            resultdf,averagedf=idmetrics()

            #violincolors=matplottabcolors
            violincolors=colorpicker()

            figsize=(10,5)
            titlefont=20
            axisfont=15
            labelfont=15
            y_padding=0.3

            cvplotinput=input.proteins_precursors_cvplot()
            cutoff95=input.removetop5percent()

            n=len(sampleconditions)
            x=np.arange(n)

            fig,ax=plt.subplots(figsize=figsize)

            medianlineprops=dict(linestyle="--",color="black")
            flierprops=dict(markersize=3)

            if cutoff95==True:
                bplot=ax.boxplot(averagedf[cvplotinput+" 95% CVs"],medianprops=medianlineprops,flierprops=flierprops)
                plot=ax.violinplot(averagedf[cvplotinput+" 95% CVs"],showextrema=False)#,showmeans=True)
                ax.set_title(cvplotinput+" CVs, 95% Cutoff",fontsize=titlefont)

            elif cutoff95==False:
                bplot=ax.boxplot(averagedf[cvplotinput+" CVs"],medianprops=medianlineprops,flierprops=flierprops)
                plot=ax.violinplot(averagedf[cvplotinput+" CVs"],showextrema=False)#,showmeans=True)
                ax.set_title(cvplotinput+" CVs",fontsize=titlefont)

            ax.set_xticks(x+1,labels=averagedf["R.Condition"],fontsize=axisfont)
            ax.tick_params(axis="y",labelsize=axisfont)
            ax.set_ylabel("CV%",fontsize=axisfont)
            ax.set_xlabel("Condition",fontsize=axisfont)
            ax.grid(linestyle="--")
            ax.set_axisbelow(True)

            ax.axhline(y=20,color="black",linestyle="--")

            for z,color in zip(plot["bodies"],violincolors):
                z.set_facecolor(color)
                z.set_edgecolor("black")
                z.set_alpha(0.7)
            return fig

    #plot counts with CV cutoffs
    @reactive.effect
    def _():
        @render.plot(width=input.countscvcutoff_width(),height=input.countscvcutoff_height())
        def countscvcutoff():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            resultdf,averagedf=idmetrics()

            figsize=(6,6)
            titlefont=20
            axisfont=15
            labelfont=15
            y_padding=0.3

            n=len(sampleconditions)
            x=np.arange(n)
            width=0.25

            cvinput=input.proteins_precursors_idcutoffplot()

            fig,ax=plt.subplots(figsize=figsize)

            ax.bar(x,averagedf[cvinput+"_avg"],width=width,label="Identified",edgecolor="k",color="#054169")
            ax.bar_label(ax.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)

            ax.bar(x+width,averagedf[cvinput+"CV<20"],width=width,label="CV<20%",edgecolor="k",color="#0071BC")
            ax.bar_label(ax.containers[1],label_type="edge",rotation=90,padding=5,fontsize=labelfont)

            ax.bar(x+(2*width),averagedf[cvinput+"CV<10"],width=width,label="CV<10%",edgecolor="k",color="#737373")
            ax.bar_label(ax.containers[2],label_type="edge",rotation=90,padding=5,fontsize=labelfont)

            ax.set_ylim(top=max(averagedf[cvinput+"_avg"])+y_padding*max(averagedf[cvinput+"_avg"]))
            #ax.legend(ncols=3,loc="upper left",fontsize=axisfont)
            ax.legend(loc='center left', bbox_to_anchor=(1, 0.5),prop={'size':axisfont})
            ax.set_xticks(x+width,sampleconditions,fontsize=axisfont,rotation=90)
            ax.tick_params(axis="y",labelsize=axisfont)
            ax.set_xlabel("Condition",fontsize=axisfont)
            ax.set_ylabel("Counts",fontsize=axisfont)
            ax.set_title(cvinput+" CV Cutoffs",fontsize=titlefont)

            ax.set_axisbelow(True)
            ax.grid(linestyle="--")
            return fig
    
    #plot unique counts per condition
    @render.plot(width=1000,height=600)
    def uniquecountsplot():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

        titlefont=20
        labelfont=15
        axisfont=15

        conditions_proteins=searchoutput[["Cond_Rep","PG.ProteinNames"]].drop_duplicates().reset_index(drop=True)

        shared=[]
        unique=[]
        for run in resultdf["Cond_Rep"].tolist():
            counter_shared=0
            counter_unique=0
            testset=conditions_proteins[conditions_proteins.Cond_Rep==run]["PG.ProteinNames"].tolist()
            rest=conditions_proteins[conditions_proteins.Cond_Rep!=run]["PG.ProteinNames"].tolist()
            for i in testset:
                if i in rest:
                    counter_shared+=1
                else:
                    counter_unique+=1
            shared.append(counter_shared)
            unique.append(counter_unique)

        fig,ax=plt.subplots()
        x=np.arange(len(resultdf["Cond_Rep"].tolist()))
        ax.bar(x,shared,label="Common IDs")
        ax.bar(x,unique,label="Unique IDs")
        ax.bar_label(ax.containers[0],label_type="edge",rotation=90,padding=-50,fontsize=labelfont)
        ax.bar_label(ax.containers[1],label_type="edge",rotation=90,padding=5,color="tab:orange",fontsize=labelfont)

        ax.set_xticks(x,labels=resultdf["Cond_Rep"].tolist(),rotation=90)
        ax.set_xlabel("Condition",fontsize=axisfont)
        ax.set_ylabel("Counts",fontsize=axisfont)
        ax.tick_params(axis="both",labelsize=axisfont)
        ax.legend(loc="center left",bbox_to_anchor=(1,0.5),fontsize=axisfont)
        ax.set_title("Unique Protein Counts",fontsize=titlefont)
        return fig

    #plot upset plot
    @reactive.effect
    def _():
        @render.plot(width=input.upsetplot_width(),height=input.upsetplot_height())
        def upsetplot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            if input.protein_precursor_pick()=="Protein":
                proteindict=dict()
                for condition in sampleconditions:
                    proteinlist=searchoutput[searchoutput["R.Condition"].str.contains(condition)][["R.Condition","PG.ProteinNames"]].drop_duplicates().reset_index(drop=True).drop(columns=["R.Condition"])
                    proteinlist.rename(columns={"PG.ProteinNames":condition},inplace=True)
                    proteindict[condition]=proteinlist[condition].tolist()
                proteins=from_contents(proteindict)

                fig=plt.figure()
                upset=UpSet(proteins,show_counts=True,sort_by="cardinality").plot(fig)
                upset["totals"].set_title("# Proteins")
                plt.ylabel("Protein Intersections",fontsize=14)
            elif input.protein_precursor_pick()=="Peptide":
                peptidedict=dict()
                for condition in sampleconditions:
                    peptidelist=searchoutput[searchoutput["R.Condition"].str.contains(condition)][["R.Condition","EG.ModifiedPeptide"]].drop_duplicates().reset_index(drop=True).drop(columns=["R.Condition"])
                    peptidelist.rename(columns={"EG.ModifiedPeptide":condition},inplace=True)
                    peptidedict[condition]=peptidelist[condition].tolist()
                peptides=from_contents(peptidedict)
                fig=plt.figure()
                upset=UpSet(peptides,show_counts=True,sort_by="cardinality").plot(fig)
                upset["totals"].set_title("# Peptides")
                plt.ylabel("Peptiede Intersections",fontsize=14)
            return fig
    
#endregion

# ============================================================================= Metrics
#region

    #plot charge states
    @reactive.effect
    def _():
        @render.plot(width=input.chargestate_width(),height=input.chargestate_height())
        def chargestateplot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            resultdf,averagedf=idmetrics()
            #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()

            chargestatecolor=colorpicker()    
            
            figsize=(12,5)
            titlefont=20
            labelfont=15
            axisfont=15
            y_padding=0.15
        
            if len(sampleconditions)==1:
                fig,ax=plt.subplots(figsize=(5,5))
                x=list(set(averagedf["Charge States"][0]))
                frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Charge States"][0]))]
                
                totals=sum(frequencies)
                for y,ele in enumerate(frequencies):
                    frequencies[y]=round((ele/totals)*100,1)
                ax.bar(x,frequencies,edgecolor="k",color=chargestatecolor)
                ax.set_title(averagedf["R.Condition"][0],fontsize=titlefont)
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                ax.bar_label(ax.containers[0],label_type="edge",padding=10,fontsize=labelfont)

                ax.set_ylim(bottom=-5,top=max(frequencies)+y_padding*max(frequencies))
                ax.tick_params(axis="both",labelsize=axisfont)
                ax.set_xticks(np.arange(1,max(x)+1,1))
                ax.set_xlabel("Charge State",fontsize=axisfont)             
                ax.set_ylabel("Frequency (%)",fontsize=axisfont)
            else:
                fig,ax=plt.subplots(nrows=1,ncols=len(sampleconditions),figsize=figsize)
                for i in range(len(sampleconditions)):
                    x=list(set(averagedf["Charge States"][i]))
                    frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Charge States"][i]))]

                    totals=sum(frequencies)
                    for y,ele in enumerate(frequencies):
                        frequencies[y]=round((ele/totals)*100,1)
                    ax[i].bar(x,frequencies,color=chargestatecolor[i],edgecolor="k")
                    ax[i].set_title(averagedf["R.Condition"][i],fontsize=titlefont)
                    ax[i].set_axisbelow(True)
                    ax[i].grid(linestyle="--")
                    ax[i].bar_label(ax[i].containers[0],label_type="edge",padding=10,fontsize=labelfont)

                    ax[i].set_ylim(bottom=-5,top=max(frequencies)+y_padding*max(frequencies))
                    ax[i].tick_params(axis="both",labelsize=axisfont)
                    ax[i].set_xticks(np.arange(1,max(x)+1,1))
                    ax[i].set_xlabel("Charge State",fontsize=axisfont)
                ax[0].set_ylabel("Frequency (%)",fontsize=axisfont)
            fig.set_tight_layout(True)

    #render ui call for dropdown for marking peptide lengths
    @render.ui
    def lengthmark_ui():
        if input.peplengthinput()=="barplot":
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            minlength=min(averagedf["Peptide Lengths"][0])
            maxlength=max(averagedf["Peptide Lengths"][0])
            opts=[item for item in range(minlength,maxlength+1)]
            opts.insert(0,0)
            return ui.input_selectize("lengthmark_pick","Pick peptide length to mark on bar plot (use 0 for maximum)",choices=opts)

    #plot peptide legnths
    @reactive.effect
    def _():
        @render.plot(width=input.peptidelength_width(),height=input.peptidelength_height())
        def peptidelengthplot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            resultdf,averagedf=idmetrics()
            #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()

            colors=colorpicker()

            titlefont=20
            axisfont=15
            labelfont=15
            y_padding=0.3

            if input.peplengthinput()=="lineplot":
                legendlist=[]
                fig,ax=plt.subplots(figsize=(6,4))
                for i in range(len(sampleconditions)):
                    x=list(set(averagedf["Peptide Lengths"][i]))
                    frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Peptide Lengths"][i]))]
                    if numconditions==1:
                        ax.plot(x,frequencies,color=colors,linewidth=2)
                    else:
                        ax.plot(x,frequencies,color=colors[i],linewidth=2)
                    legendlist.append(averagedf["R.Condition"][i])
                ax.tick_params(axis="both",labelsize=axisfont)
                ax.set_xlabel("Peptide Length",fontsize=titlefont)
                ax.set_ylabel("Counts",fontsize=titlefont)
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                ax.legend(legendlist,fontsize=axisfont)
            if input.peplengthinput()=="barplot":
                lengthmark=int(input.lengthmark_pick())
                if len(sampleconditions)==1:
                    fig,ax=plt.subplots(figsize=(5,5))
                    x=list(set(averagedf["Peptide Lengths"][0]))
                    frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Peptide Lengths"][0]))]
                    ax.bar(x,frequencies,color=colors,edgecolor="k")
                    ax.set_title(averagedf["R.Condition"][0],fontsize=titlefont)
                    ax.set_axisbelow(True)
                    ax.grid(linestyle="--")
                    if lengthmark!=0:
                        ax.vlines(x=x[lengthmark-min(x)],ymin=frequencies[lengthmark-min(x)],ymax=frequencies[lengthmark-min(x)]+0.2*frequencies[lengthmark-min(x)],color="k")
                        ax.text(x=x[lengthmark-min(x)],y=frequencies[lengthmark-min(x)]+0.2*frequencies[lengthmark-min(x)],s=str(x[lengthmark-min(x)])+", "+str(frequencies[lengthmark-min(x)]),fontsize=labelfont)
                    elif lengthmark==0:
                        ax.vlines(x=x[np.argmax(frequencies)],ymin=max(frequencies),ymax=max(frequencies)+0.2*max(frequencies),color="k")
                        ax.text(x=x[np.argmax(frequencies)],y=max(frequencies)+0.2*max(frequencies),s=str(x[np.argmax(frequencies)])+", "+str(max(frequencies)),fontsize=labelfont)
                    ax.set_ylim(top=max(frequencies)+y_padding*max(frequencies))
                    ax.tick_params(axis="both",labelsize=axisfont)
                    ax.set_xticks(np.arange(5,max(x)+1,5))
                    ax.set_xlabel("Peptide Length",fontsize=axisfont)
                    ax.set_ylabel("Counts",fontsize=axisfont)
                else:
                    fig,ax=plt.subplots(nrows=1,ncols=len(sampleconditions),figsize=(15,5))
                    for i in range(len(sampleconditions)):
                        x=list(set(averagedf["Peptide Lengths"][i]))
                        frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Peptide Lengths"][i]))]
                        ax[i].bar(x,frequencies,color=colors[i],edgecolor="k")
                        ax[i].set_title(averagedf["R.Condition"][i],fontsize=titlefont)
                        ax[i].set_axisbelow(True)
                        ax[i].grid(linestyle="--")
                        if lengthmark!=0:
                            ax[i].vlines(x=x[lengthmark-min(x)],ymin=frequencies[lengthmark-min(x)],ymax=frequencies[lengthmark-min(x)]+0.2*frequencies[lengthmark-min(x)],color="k")
                            ax[i].text(x=x[lengthmark-min(x)],y=frequencies[lengthmark-min(x)]+0.2*frequencies[lengthmark-min(x)],s=str(x[lengthmark-min(x)])+", "+str(frequencies[lengthmark-min(x)]),fontsize=labelfont)
                        elif lengthmark==0:
                            ax[i].vlines(x=x[np.argmax(frequencies)],ymin=max(frequencies),ymax=max(frequencies)+0.2*max(frequencies),color="k")
                            ax[i].text(x=x[np.argmax(frequencies)],y=max(frequencies)+0.2*max(frequencies),s=str(x[np.argmax(frequencies)])+", "+str(max(frequencies)),fontsize=labelfont)
                        ax[i].set_ylim(top=max(frequencies)+y_padding*max(frequencies))
                        ax[i].tick_params(axis="both",labelsize=axisfont)
                        ax[i].set_xticks(np.arange(5,max(x)+1,5))
                        ax[i].set_xlabel("Peptide Length",fontsize=axisfont)
                    ax[0].set_ylabel("Counts",fontsize=axisfont)
            fig.set_tight_layout(True)
            return fig
    
    #plot peptides per protein
    @reactive.effect
    def _():
        @render.plot(width=input.pepsperprotein_width(),height=input.pepsperprotein_height())
        def pepsperproteinplot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            resultdf,averagedf=idmetrics()
            #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()

            colors=colorpicker()

            titlefont=20
            axisfont=15
            labelfont=15

            if input.pepsperproteininput()=="lineplot":
                legendlist=[]
                fig,ax=plt.subplots(figsize=(6,4))
                for i in range(len(sampleconditions)):
                    x=list(set(averagedf["Peptides per Protein"][i]))
                    frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Peptides per Protein"][i]))]
                    if numconditions==1:
                        ax.plot(x,frequencies,color=colors,linewidth=2)
                    else:
                        ax.plot(x,frequencies,color=colors[i],linewidth=2)
                    legendlist.append(averagedf["R.Condition"][i])
                ax.tick_params(axis="both",labelsize=axisfont)
                ax.set_xlabel("Peptides per Protein",fontsize=titlefont)
                ax.set_ylabel("Counts",fontsize=titlefont)
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                ax.legend(legendlist,fontsize=axisfont)

            if input.pepsperproteininput()=="barplot":
                if len(sampleconditions)==1:
                    fig,ax=plt.subplots(figsize=(5,5))
                    for i in range(len(sampleconditions)):
                        x=list(set(averagedf["Peptides per Protein"][0]))
                        frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Peptides per Protein"][0]))]

                        ax.bar(x,frequencies,color=colors,width=0.025)
                        ax.set_title(averagedf["R.Condition"][0],fontsize=titlefont)
                        ax.set_axisbelow(True)
                        ax.grid(linestyle="--")

                        ax.tick_params(axis="both",labelsize=axisfont)
                        ax.set_xticks(np.arange(0,max(x)+1,25))
                        ax.set_xlabel("# Peptides",fontsize=axisfont)
                        ax.set_ylabel("Counts",fontsize=axisfont)
                else:
                    fig,ax=plt.subplots(nrows=1,ncols=len(sampleconditions),figsize=(15,5))
                    for i in range(len(sampleconditions)):
                        x=list(set(averagedf["Peptides per Protein"][i]))
                        frequencies=[len(list(group)) for key, group in groupby(sorted(averagedf["Peptides per Protein"][i]))]

                        ax[i].bar(x,frequencies,color=colors[i])
                        ax[i].set_title(averagedf["R.Condition"][i],fontsize=titlefont)
                        ax[i].set_axisbelow(True)
                        ax[i].grid(linestyle="--")

                        ax[i].tick_params(axis="both",labelsize=axisfont)
                        ax[i].set_xticks(np.arange(0,max(x)+1,25))
                        ax[i].set_xlabel("# Peptides",fontsize=axisfont)
                    ax[0].set_ylabel("Counts",fontsize=axisfont)
                fig.set_tight_layout(True)
            return fig
    
    #plot dynamic range
    @render.plot(width=500,height=700)
    def dynamicrangeplot():
        conditioninput=input.conditionname()
        propertyinput=input.meanmedian()
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

        markersize=25
        titlefont=20

        if propertyinput=="mean":
            intensitydf=searchoutput[searchoutput["R.Condition"].str.contains(conditioninput)][["PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates().groupby("PG.ProteinNames").mean().reset_index(drop=True)
        elif propertyinput=="median":
            intensitydf=searchoutput[searchoutput["R.Condition"].str.contains(conditioninput)][["PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates().groupby("PG.ProteinNames").median().reset_index(drop=True)

        fig,ax=plt.subplots(nrows=2,ncols=1,figsize=(5,7),sharex=True,gridspec_kw={"height_ratios":[1,3]})
        ax1=ax[0]
        ax2=ax[1]

        maxintensity=intensitydf.max()
        relative_fraction=(1-(intensitydf/maxintensity)).sort_values(by="PG.MS2Quantity").reset_index(drop=True)
        n_25=relative_fraction[relative_fraction["PG.MS2Quantity"]<0.25].shape[0]
        n_50=relative_fraction[relative_fraction["PG.MS2Quantity"]<0.50].shape[0]
        n_75=relative_fraction[relative_fraction["PG.MS2Quantity"]<0.75].shape[0]

        ax1.scatter(relative_fraction.index,relative_fraction["PG.MS2Quantity"],marker=".",s=markersize)
        ax1.set_ylabel("Relative Fraction")
        ax1.text(0,0.2,"- - - - - - - "+str(n_25)+" Protein groups")
        ax1.text(0,0.45,"- - - - - - - "+str(n_50)+" Protein groups")
        ax1.text(0,0.7,"- - - - - - - "+str(n_75)+" Protein groups")

        log10df=np.log10(intensitydf).sort_values(by="PG.MS2Quantity",ascending=False).reset_index(drop=True)
        dynamicrange=round(max(log10df["PG.MS2Quantity"])-min(log10df["PG.MS2Quantity"]),1)
        ax2.scatter(log10df.index,log10df["PG.MS2Quantity"],marker=".",s=markersize)
        ax2.set_ylabel("Log10(Area)")
        ax2.text(max(log10df.index)-0.6*(max(log10df.index)),max(log10df["PG.MS2Quantity"])-0.15*(max(log10df["PG.MS2Quantity"])),str(dynamicrange)+" log",fontsize=titlefont)

        plt.xlabel("Rank")
        plt.suptitle(conditioninput+" ("+propertyinput+"_PG)",x=0.13,horizontalalignment="left")
        ax1.set_axisbelow(True)
        ax2.set_axisbelow(True)
        ax1.grid(linestyle="--")
        ax2.grid(linestyle="--")
        plt.tight_layout()
        return fig
    
    #plot data completeness
    @reactive.effect
    def _():
        @render.plot(width=input.datacompleteness_width(),height=input.datacompleteness_height())
        def datacompletenessplot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

            figsize=(12,5)
            titlefont=20
            axisfont=15
            labelfont=15
            y_padding=0.3
            labelpadding=3

            color1="tab:blue"
            color2="black"
            if input.protein_peptide()=="proteins":
                proteincounts=[len(list(group)) for key, group in groupby(sorted(searchoutput[["R.Condition","R.Replicate","PG.ProteinGroups"]].drop_duplicates().drop(columns=["R.Condition","R.Replicate"]).reset_index(drop=True).groupby(["PG.ProteinGroups"]).size().tolist()))]

            elif input.protein_peptide()=="peptides":
                proteincounts=[len(list(group)) for key, group in groupby(sorted(searchoutput[["R.Condition","R.Replicate","PEP.StrippedSequence"]].drop_duplicates().drop(columns=["R.Condition","R.Replicate"]).reset_index(drop=True).groupby(["PEP.StrippedSequence"]).size().tolist()))]

            totalproteins=sum(proteincounts)

            proteinfrequencies=[]
            for i in proteincounts:
                proteinfrequencies.append(i/totalproteins*100)

            xaxis=np.arange(1,len(proteinfrequencies)+1,1).tolist()

            y1=proteincounts
            y2=proteinfrequencies

            fig,ax1 = plt.subplots(figsize=figsize)

            ax2 = ax1.twinx()
            ax1.bar(xaxis, y1,edgecolor="k")
            ax2.plot(xaxis, y2,"-o",color=color2)

            ax1.set_xlabel('Observed in X Runs',fontsize=axisfont)
            if input.protein_peptide()=="proteins":
                ax1.set_ylabel('# Proteins',color=color1,fontsize=axisfont)
            elif input.protein_peptide()=="peptides":
                ax1.set_ylabel('# Peptides',color=color1,fontsize=axisfont)
            ax2.set_ylabel('% of MS Runs',color=color2,fontsize=axisfont)
            ax1.tick_params(axis="x",labelsize=axisfont)
            ax1.tick_params(axis="y",colors=color1,labelsize=axisfont)
            ax2.tick_params(axis="y",colors=color2,labelsize=axisfont)

            ax1.bar_label(ax1.containers[0],label_type="edge",padding=35,color=color1,fontsize=labelfont)
            ax1.set_ylim(top=max(proteincounts)+y_padding*max(proteincounts))
            ax2.set_ylim(top=max(proteinfrequencies)+y_padding*max(proteinfrequencies))

            for x,y in enumerate(proteinfrequencies):
                ax2.text(xaxis[x],proteinfrequencies[x]+labelpadding,str(round(y,1))+"%",
                horizontalalignment="center",verticalalignment="bottom",color=color2,fontsize=labelfont)

            ax1.set_axisbelow(True)
            ax1.grid(linestyle="--")
            plt.xticks(range(1,len(xaxis)+1))
            plt.xlim(0.5,len(xaxis)+1)
            return fig

#endregion

#  ============================================================================ PTMs 
#region

    #function for finding the PTMs in the data
    @reactive.calc
    def find_ptms():
        searchoutput=metadata_update()
        peplist=searchoutput["EG.ModifiedPeptide"]
        ptmlist=[]
        for i in peplist:
            ptmlist.append(re.findall(r"[^[]*\[([^]]*)\]",i))
        searchoutput["PTMs"]=ptmlist
        return(list(OrderedDict.fromkeys(itertools.chain(*ptmlist))))
    
    #function for doing ID calculations for a picked PTM
    #ptmresultdf,ptm=ptmcounts()
    @reactive.calc
    def ptmcounts():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        resultdf,averagedf=idmetrics()
        ptm=input.foundptms()

        numptmproteins=[]
        numptmproteins2pepts=[]
        numptmpeptides=[]
        numptmprecursors=[]
        for condition in sampleconditions:
            for j in range(max(maxreplicatelist)+1):
                df=searchoutput[searchoutput["R.Condition"].str.contains(condition)&(searchoutput["R.Replicate"]==j)][["R.Condition","R.Replicate","PG.ProteinNames","PG.MS2Quantity","EG.ModifiedPeptide","FG.Charge","FG.MS2Quantity"]]
                if df.empty:
                    continue
                #number of proteins with specified PTM
                numptmproteins.append(len(df[df["EG.ModifiedPeptide"].str.contains(ptm)][["PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates()))

                #number of proteins with 2 peptides and specified PTM
                numptmproteins2pepts.append(len(df[df["EG.ModifiedPeptide"].str.contains(ptm)][["PG.ProteinNames","EG.ModifiedPeptide"]].drop_duplicates().groupby("PG.ProteinNames").size().reset_index(name="peptides").query("peptides>1")))

                #number of peptides with specified PTM
                numptmpeptides.append(len(df[df["EG.ModifiedPeptide"].str.contains(ptm)][["EG.ModifiedPeptide"]].drop_duplicates()))

                #number of precursors with specified PTM
                numptmprecursors.append(len(df[df["EG.ModifiedPeptide"].str.contains(ptm)][["EG.ModifiedPeptide"]]))

        ptmresultdf=pd.DataFrame({"Cond_Rep":resultdf["Cond_Rep"],"proteins":numptmproteins,"proteins2pepts":numptmproteins2pepts,"peptides":numptmpeptides,"precursors":numptmprecursors})

        propcolumnlist=["proteins","proteins2pepts","peptides","precursors"]

        for column in propcolumnlist:
            exec(f'ptmresultdf["{column}_enrich%"]=round((ptmresultdf["{column}"]/resultdf["{column}"])*100,1)')
        return ptmresultdf,ptm

    #generate list to pull from to pick PTMs
    @render.ui
    def ptmlist_ui():
        listofptms=find_ptms()
        ptmshortened=[]
        for i in range(len(listofptms)):
            ptmshortened.append(re.sub(r'\(.*?\)',"",listofptms[i]))
        ptmdict={ptmshortened[i]: listofptms[i] for i in range(len(listofptms))}
        return ui.input_selectize("foundptms","Pick PTM to plot data for",choices=ptmdict,selected=listofptms[0])

    #plot PTM ID metrics
    @reactive.effect
    def _():
        plotinput=input.ptmidplotinput()
        if plotinput=="all":
            @render.plot(width=input.ptmidmetrics_width(),height=input.ptmidmetrics_height())
            def ptmidmetricsplot():
                #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()
                #idmetricscolor=tabcolorsblocks

                idmetricscolor=replicatecolors()

                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.3

                ptmresultdf,ptm=ptmcounts()

                fig,ax=plt.subplots(nrows=2,ncols=2,figsize=figsize,sharex=True)
                fig.set_tight_layout(True)
                ax1=ax[0,0]
                ax2=ax[0,1]
                ax3=ax[1,0]
                ax4=ax[1,1]

                ptmresultdf.plot.bar(ax=ax1,x="Cond_Rep",y="proteins",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax1.bar_label(ax1.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax1.set_ylim(top=max(ptmresultdf["proteins"].tolist())+y_padding*max(ptmresultdf["proteins"].tolist()))
                ax1.set_title("Proteins",fontsize=titlefont)

                ptmresultdf.plot.bar(ax=ax2,x="Cond_Rep",y="proteins2pepts",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax2.bar_label(ax2.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax2.set_ylim(top=max(ptmresultdf["proteins2pepts"].tolist())+y_padding*max(ptmresultdf["proteins2pepts"].tolist()))
                ax2.set_title("Proteins2Pepts",fontsize=titlefont)

                ptmresultdf.plot.bar(ax=ax3,x="Cond_Rep",y="peptides",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax3.bar_label(ax3.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax3.set_ylim(top=max(ptmresultdf["peptides"].tolist())+(y_padding+0.1)*max(ptmresultdf["peptides"].tolist()))
                ax3.set_title("Peptides",fontsize=titlefont)
                ax3.set_xlabel("Condition",fontsize=titlefont)
                ax3.set_ylabel("  ",fontsize=titlefont)

                ptmresultdf.plot.bar(ax=ax4,x="Cond_Rep",y="precursors",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax4.bar_label(ax4.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax4.set_ylim(top=max(ptmresultdf["precursors"].tolist())+(y_padding+0.1)*max(ptmresultdf["precursors"].tolist()))
                ax4.set_title("Precursors",fontsize=titlefont)
                ax4.set_xlabel("Condition",fontsize=titlefont)

                fig.text(0, 0.6,"Counts",ha="left",va="center",rotation="vertical",fontsize=titlefont)

                ax1.set_axisbelow(True)
                ax1.grid(linestyle="--")
                ax2.set_axisbelow(True)
                ax2.grid(linestyle="--")
                ax3.set_axisbelow(True)
                ax3.grid(linestyle="--")
                ax4.set_axisbelow(True)
                ax4.grid(linestyle="--")
                plt.suptitle("ID Counts for PTM: "+ptm,y=1,fontsize=titlefont)
            
        else:
            @render.plot(width=input.ptmidmetrics_width(),height=input.ptmidmetrics_height())
            def ptmidmetricsplot():
                idmetricscolor=replicatecolors()

                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.3

                ptmresultdf,ptm=ptmcounts()
                fig,ax=plt.subplots()
                ptmresultdf.plot.bar(ax=ax,x="Cond_Rep",y=plotinput,legend=False,width=0.8,color=idmetricscolor,edgecolor="k")
                ax.bar_label(ax.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax.set_ylim(top=max(ptmresultdf[plotinput].tolist())+y_padding*max(ptmresultdf[plotinput].tolist()))
                plt.ylabel("Counts",fontsize=axisfont)
                plt.xlabel("Condition",fontsize=axisfont)
                plt.title(plotinput,fontsize=titlefont)
                ax.tick_params(axis="both",labelsize=axisfont)
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                plt.suptitle("ID Counts for PTM: "+ptm,y=1,fontsize=titlefont)

    #plot PTM enrichment
    @reactive.effect
    def _():
        plotinput=input.ptmenrichplotinput()
        if plotinput=="all":
            @render.plot(width=input.ptmenrichment_width(),height=input.ptmenrichment_height())
            def ptmenrichment():
                #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()
                #idmetricscolor=tabcolorsblocks
                idmetricscolor=replicatecolors()
                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.3

                ptmresultdf,ptm=ptmcounts()

                fig,ax=plt.subplots(nrows=2,ncols=2,figsize=figsize,sharex=True)
                fig.set_tight_layout(True)
                ax1=ax[0,0]
                ax2=ax[0,1]
                ax3=ax[1,0]
                ax4=ax[1,1]

                ptmresultdf.plot.bar(ax=ax1,x="Cond_Rep",y="proteins_enrich%",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax1.bar_label(ax1.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax1.set_ylim(top=max(ptmresultdf["proteins_enrich%"].tolist())+y_padding*max(ptmresultdf["proteins_enrich%"].tolist()))
                ax1.set_title("Proteins",fontsize=titlefont)

                ptmresultdf.plot.bar(ax=ax2,x="Cond_Rep",y="proteins2pepts_enrich%",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax2.bar_label(ax2.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax2.set_ylim(top=max(ptmresultdf["proteins2pepts_enrich%"].tolist())+y_padding*max(ptmresultdf["proteins2pepts_enrich%"].tolist()))
                ax2.set_title("Proteins2Pepts",fontsize=titlefont)

                ptmresultdf.plot.bar(ax=ax3,x="Cond_Rep",y="peptides_enrich%",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax3.bar_label(ax3.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax3.set_ylim(top=max(ptmresultdf["peptides_enrich%"].tolist())+y_padding*max(ptmresultdf["peptides_enrich%"].tolist()))
                ax3.set_title("Peptides",fontsize=titlefont)
                ax3.set_xlabel("Condition",fontsize=titlefont)
                ax3.set_ylabel("  ",fontsize=titlefont)

                ptmresultdf.plot.bar(ax=ax4,x="Cond_Rep",y="precursors_enrich%",legend=False,width=0.8,color=idmetricscolor,edgecolor="k",fontsize=axisfont)
                ax4.bar_label(ax4.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax4.set_ylim(top=max(ptmresultdf["precursors_enrich%"].tolist())+y_padding*max(ptmresultdf["precursors_enrich%"].tolist()))
                ax4.set_title("Precursors",fontsize=titlefont)
                ax4.set_xlabel("Condition",fontsize=titlefont)

                fig.text(0.01, 0.6,"Enrichment %",ha="center",va="center",rotation="vertical",fontsize=titlefont)

                ax1.set_axisbelow(True)
                ax1.grid(linestyle="--")
                ax2.set_axisbelow(True)
                ax2.grid(linestyle="--")
                ax3.set_axisbelow(True)
                ax3.grid(linestyle="--")
                ax4.set_axisbelow(True)
                ax4.grid(linestyle="--")
                plt.suptitle("Enrichment for PTM: "+ptm,y=1,fontsize=titlefont)
            
        else:
            @render.plot(width=input.ptmenrichment_width(),height=input.ptmenrichment_height())
            def ptmenrichment():
                idmetricscolor=replicatecolors()
                figsize=(15,10)
                titlefont=20
                axisfont=15
                labelfont=15
                y_padding=0.3

                ptmresultdf,ptm=ptmcounts()

                fig,ax=plt.subplots()
                ptmresultdf.plot.bar(ax=ax,x="Cond_Rep",y=str(plotinput+"_enrich%"),legend=False,width=0.8,color=idmetricscolor,edgecolor="k")
                ax.bar_label(ax.containers[0],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
                ax.set_ylim(top=max(ptmresultdf[str(plotinput+"_enrich%")].tolist())+y_padding*max(ptmresultdf[str(plotinput+"_enrich%")].tolist()))
                plt.ylabel("Enrichment %",fontsize=axisfont)
                plt.xlabel("Condition",fontsize=axisfont)
                plt.title(str(plotinput+" enrichment %"),fontsize=titlefont)
                ax.tick_params(axis="both",labelsize=axisfont)
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                plt.suptitle("Enrichment for PTM: "+ptm,y=1,fontsize=titlefont)

    #plot PTM CV violin plots
    @reactive.effect
    def _():
        @render.plot(width=input.ptmcvplot_width(),height=input.ptmcvplot_height())
        def ptm_cvplot():
            #colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            resultdf,averagedf=idmetrics()
            ptmresultdf,ptm=ptmcounts()
            colors=colorpicker()
            cvplotinput=input.ptm_proteins_precursors()
            cutoff95=input.ptm_removetop5percent()
            
            figsize=(15,10)
            titlefont=20
            axisfont=15
            labelfont=15
            y_padding=0.3

            ptmcvs=pd.DataFrame()
            ptmcvs["R.Condition"]=averagedf["R.Condition"]
            proteincv=[]
            proteinptmcv95=[]
            precursorcv=[]
            precursorptmcv95=[]

            df=searchoutput[["R.Condition","R.Replicate","PG.ProteinNames","PG.MS2Quantity","FG.Charge","EG.ModifiedPeptide","FG.MS2Quantity"]].drop_duplicates().reset_index(drop=True)
            for x,condition in enumerate(averagedf["R.Condition"]):
                ptmdf=df[df["R.Condition"].str.contains(condition)][["R.Condition","R.Replicate","PG.ProteinNames","PG.MS2Quantity","FG.Charge","EG.ModifiedPeptide","FG.MS2Quantity"]].drop_duplicates().reset_index(drop=True)
                
                if maxreplicatelist[x]==1:
                    emptylist=[]
                    proteincv.append(emptylist)
                    proteinptmcv95.append(emptylist)
                    precursorcv.append(emptylist)
                    precursorptmcv95.append(emptylist)
                else:
                    #protein CVs for specified PTMs
                    mean=ptmdf[ptmdf["EG.ModifiedPeptide"].str.contains(ptm)!=False][["R.Condition","PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates().groupby(["R.Condition","PG.ProteinNames"]).mean().rename(columns={"PG.MS2Quantity":"PTM Protein Mean"}).reset_index(drop=True)
                    stdev=ptmdf[ptmdf["EG.ModifiedPeptide"].str.contains(ptm)!=False][["R.Condition","PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates().groupby(["R.Condition","PG.ProteinNames"]).std().rename(columns={"PG.MS2Quantity":"PTM Protein Stdev"}).reset_index(drop=True)
                    cvptmproteintable=pd.concat([mean,stdev],axis=1)
                    cvptmproteintable["PTM CV"]=(cvptmproteintable["PTM Protein Stdev"]/cvptmproteintable["PTM Protein Mean"]*100).tolist()
                    cvptmproteintable.drop(columns=["PTM Protein Mean","PTM Protein Stdev"],inplace=True)
                    cvptmproteintable.dropna(inplace=True)
                    proteincv.append(cvptmproteintable["PTM CV"].tolist())
                    top95=np.percentile(cvptmproteintable,95)
                    ptmcvlist95=[]
                    for i in cvptmproteintable["PTM CV"].tolist():
                        if i <=top95:
                            ptmcvlist95.append(i)
                    proteinptmcv95.append(ptmcvlist95)
                    
                    #precursor CVs for specified PTMs
                    mean=ptmdf[ptmdf["EG.ModifiedPeptide"].str.contains(ptm)!=False][["R.Condition","EG.ModifiedPeptide","FG.Charge","FG.MS2Quantity"]].groupby(["R.Condition","EG.ModifiedPeptide","FG.Charge"]).mean().rename(columns={"FG.MS2Quantity":"PTM Precursor Mean"}).reset_index(drop=True)
                    stdev=ptmdf[ptmdf["EG.ModifiedPeptide"].str.contains(ptm)!=False][["R.Condition","EG.ModifiedPeptide","FG.Charge","FG.MS2Quantity"]].groupby(["R.Condition","EG.ModifiedPeptide","FG.Charge"]).std().rename(columns={"FG.MS2Quantity":"PTM Precursor Stdev"}).reset_index(drop=True)
                    cvptmprecursortable=pd.concat([mean,stdev],axis=1)
                    cvptmprecursortable["PTM CV"]=(cvptmprecursortable["PTM Precursor Stdev"]/cvptmprecursortable["PTM Precursor Mean"]*100).tolist()
                    cvptmprecursortable.drop(columns=["PTM Precursor Mean","PTM Precursor Stdev"],inplace=True)
                    cvptmprecursortable.dropna(inplace=True)
                    precursorcv.append(cvptmprecursortable["PTM CV"].tolist())
                    top95=np.percentile(cvptmprecursortable,95)
                    ptmcvlist95=[]
                    for i in cvptmprecursortable["PTM CV"].tolist():
                        if i <=top95:
                            ptmcvlist95.append(i)
                    precursorptmcv95.append(ptmcvlist95)
            ptmcvs["Protein CVs"]=proteincv
            ptmcvs["Protein 95% CVs"]=proteinptmcv95
            ptmcvs["Precursor CVs"]=precursorcv
            ptmcvs["Precursor 95% CVs"]=precursorptmcv95

            n=len(sampleconditions)
            x=np.arange(n)

            fig,ax=plt.subplots(figsize=figsize)

            medianlineprops=dict(linestyle="--",color="black")
            flierprops=dict(markersize=3)

            if cutoff95==True:
                bplot=ax.boxplot(ptmcvs[cvplotinput+" 95% CVs"],medianprops=medianlineprops,flierprops=flierprops)
                plot=ax.violinplot(ptmcvs[cvplotinput+" 95% CVs"],showextrema=False)#,showmeans=True)
                ax.set_title(cvplotinput+" CVs for PTM: "+ptm+", 95% Cutoff",fontsize=titlefont)

            elif cutoff95==False:
                bplot=ax.boxplot(ptmcvs[cvplotinput+" CVs"],medianprops=medianlineprops,flierprops=flierprops)
                plot=ax.violinplot(ptmcvs[cvplotinput+" CVs"],showextrema=False)#,showmeans=True)
                ax.set_title(cvplotinput+" CVs for PTM: "+ptm,fontsize=titlefont)

            ax.set_xticks(x+1,labels=ptmcvs["R.Condition"],fontsize=axisfont)
            ax.tick_params(axis="y",labelsize=axisfont)
            ax.set_ylabel("CV%",fontsize=axisfont)
            ax.set_xlabel("Condition",fontsize=axisfont)
            ax.grid(linestyle="--")
            ax.set_axisbelow(True)

            ax.axhline(y=20,color="black",linestyle="--")

            for z,color in zip(plot["bodies"],colors):
                z.set_facecolor(color)
                z.set_edgecolor("black")
                z.set_alpha(0.7)

    #plot PTMs per precursor
    @reactive.effect
    def _():
        width=input.barwidth()
        @render.plot(width=input.ptmsperprecursor_width(),height=input.ptmsperprecursor_height())
        def ptmsperprecursor():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            resultdf,averagedf=idmetrics()

            colors=colorpicker()

            y_padding=0.3
            titlefont=20
            axisfont=15
            labelfont=15

            fig,ax=plt.subplots()
            ptmdf=pd.DataFrame()

            for j,condition in enumerate(sampleconditions):
                df=searchoutput[searchoutput["R.Condition"].str.contains(condition)][["EG.ModifiedPeptide","FG.Charge"]].drop_duplicates().reset_index(drop=True)
                dfptmlist=[]
                numptms=[]
                for i in df["EG.ModifiedPeptide"]:
                    foundptms=re.findall(r"[^[]*\[([^]]*)\]",i)
                    dfptmlist.append(foundptms)
                    numptms.append(len(foundptms))
                dfptmlist=pd.Series(dfptmlist).value_counts().to_frame().reset_index().rename(columns={"index":condition,"count":condition+"_count"})
                ptmdf=pd.concat([ptmdf,dfptmlist],axis=1)
                
                x=np.arange(0,max(numptms)+1,1)
                frequencies=pd.Series(numptms).value_counts()
                if numconditions==1:
                    ax.bar(x+(j*width),frequencies,width=width,color=colors,edgecolor="black")
                else:
                    ax.bar(x+(j*width),frequencies,width=width,color=colors[j],edgecolor="black")
                ax.bar_label(ax.containers[j],label_type="edge",rotation=90,padding=5,fontsize=labelfont)

            ax.legend(sampleconditions,loc="upper right",fontsize=axisfont)
            ax.set_ylim(bottom=-1000,top=max(frequencies)+y_padding*max(frequencies))
            ax.set_xticks(x+width/2,x)
            ax.tick_params(axis="both",labelsize=axisfont)
            ax.set_ylabel("Counts",fontsize=axisfont)
            ax.set_xlabel("# of PTMs",fontsize=axisfont)
            ax.set_title("# of PTMs per Precursor",fontsize=titlefont)
            ax.set_axisbelow(True)
            ax.grid(linestyle="--")

            return fig

#endregion    

# ============================================================================= Heatmaps
#region

    @render.ui
    def cond_rep_list_heatmap():
        if input.conditiontype()=="replicate":
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            opts=resultdf["Cond_Rep"].tolist()
            return ui.input_selectize("cond_rep_heatmap","Pick run to show:",choices=opts)               
        elif input.conditiontype()=="condition":
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            opts=resultdf["R.Condition"].tolist()
            return ui.input_selectize("cond_rep_heatmap","Pick condition to show:",choices=opts)   

    #plot 2D heatmaps for RT, m/z, mobility
    @render.plot(width=1400,height=1000)
    def replicate_heatmap():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

        titlefont=20
        figsize=(15,10)

        numbins=input.heatmap_numbins()

        conditioninput=input.cond_rep_heatmap()
        if input.conditiontype()=="replicate":
            his2dsample=searchoutput[searchoutput["Cond_Rep"].str.contains(conditioninput)][["Cond_Rep","EG.IonMobility","EG.ApexRT","FG.PrecMz","FG.MS2Quantity"]].sort_values(by="EG.ApexRT").reset_index(drop=True)
        elif input.conditiontype()=="condition":
            his2dsample=searchoutput[searchoutput["R.Condition"].str.contains(conditioninput)][["R.Condition","EG.IonMobility","EG.ApexRT","FG.PrecMz","FG.MS2Quantity"]].sort_values(by="EG.ApexRT").reset_index(drop=True)

        samplename=conditioninput
        cmap=matplotlib.colors.LinearSegmentedColormap.from_list("",["white","blue","red"])

        fig,ax=plt.subplots(nrows=2,ncols=2,figsize=figsize)

        i=ax[0,0].hist2d(his2dsample["EG.ApexRT"],his2dsample["FG.PrecMz"],bins=numbins,cmap=cmap)
        ax[0,0].set_title("RT vs m/z")
        ax[0,0].set_xlabel("Retention Time (min)")
        ax[0,0].set_ylabel("m/z")
        fig.colorbar(i[3],ax=ax[0,0])

        j=ax[0,1].hist2d(his2dsample["FG.PrecMz"],his2dsample["EG.IonMobility"],bins=numbins,cmap=cmap)
        ax[0,1].set_title("m/z vs Mobility")
        ax[0,1].set_xlabel("m/z")
        ax[0,1].set_ylabel("Ion Mobility ($1/K_{0}$)")
        fig.colorbar(j[3],ax=ax[0,1])

        ax[1,0].plot(his2dsample["EG.ApexRT"],his2dsample["FG.MS2Quantity"],color="blue",linewidth=0.5)
        ax[1,0].set_title("RT vs Intensity (line plot)")
        ax[1,0].set_xlabel("Retention Time (min)")
        ax[1,0].set_ylabel("Intensity")

        k=ax[1,1].hist2d(his2dsample["EG.ApexRT"].sort_values(),his2dsample["EG.IonMobility"],bins=numbins,cmap=cmap)
        ax[1,1].set_title("RT vs Mobility")
        ax[1,1].set_xlabel("Retention Time (min)")
        ax[1,1].set_ylabel("Ion Mobility ($1/K_{0}$)")
        fig.colorbar(k[3],ax=ax[1,1])
        fig.set_tight_layout(True)
        plt.suptitle("Histograms of Identified Peptides"+", "+samplename,y=1,fontsize=titlefont)

    #imported DIA windows
    def diawindows_import():
        diawindows=input.diawindow_upload()
        if diawindows is None:
            return pd.DataFrame()
        diawindows=diawindows.drop(index=0).reset_index(drop=True)
        startcoords=[]
        for i in range(len(diawindows)):
            startcorner=float(diawindows["Start Mass [m/z]"][i]),float(diawindows["Start IM [1/K0]"][i])
            startcoords.append(startcorner)
        diawindows["W"]=diawindows["End Mass [m/z]"].astype(float)-diawindows["Start Mass [m/z]"].astype(float)
        diawindows["H"]=diawindows["End IM [1/K0]"].astype(float)-diawindows["Start IM [1/K0]"].astype(float)
        diawindows["xy"]=startcoords
        return diawindows
    #Lubeck DIA windows
    def lubeckdiawindow():
        lubeckdia=pd.DataFrame({
            "#MS Type":['PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF'],
            "Cycle Id":[1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14, 14, 14, 15, 15, 15, 16, 16, 16, 17, 17, 17, 18, 18, 18, 19, 19, 19, 20, 20, 20],
            "Start IM [1/K0]":[0.965, 0.805, 0.6, 0.977, 0.87, 0.6, 0.986, 0.89, 0.6, 0.995, 0.9, 0.6, 1.006, 0.906, 0.6, 1.025, 0.91, 0.6, 1.045, 0.917, 0.6, 1.064, 0.927, 0.6, 1.085, 0.94, 0.6, 1.105, 0.955, 0.6, 0.97, 0.85, 0.6, 0.982, 0.884, 0.6, 0.99, 0.895, 0.6, 1.0, 0.903, 0.6, 1.015, 0.908, 0.6, 1.034, 0.914, 0.6, 1.054, 0.92, 0.6, 1.075, 0.934, 0.6, 1.095, 0.947, 0.6, 1.11, 0.96, 0.6],
            "End IM [1/K0]":[1.12, 0.965, 0.805, 1.15, 0.977, 0.87, 1.19, 0.986, 0.89, 1.23, 0.995, 0.9, 1.27, 1.006, 0.906, 1.31, 1.025, 0.91, 1.35, 1.045, 0.917, 1.39, 1.064, 0.927, 1.43, 1.085, 0.94, 1.45, 1.105, 0.955, 1.13, 0.97, 0.85, 1.17, 0.982, 0.884, 1.21, 0.99, 0.895, 1.25, 1.0, 0.903, 1.29, 1.015, 0.908, 1.33, 1.034, 0.914, 1.37, 1.054, 0.92, 1.41, 1.075, 0.934, 1.44, 1.095, 0.947, 1.45, 1.11, 0.96],
            "Start Mass [m/z]":[725.13, 559.8, 350.68, 746.34, 574.21, 412.39, 769.41, 588.81, 437.42, 794.87, 603.8, 456.05, 821.43, 619.33, 472.76, 851.93, 635.35, 488.1, 886.49, 651.86, 502.77, 928.86, 668.83, 517.08, 982.67, 686.35, 531.29, 1059.54, 704.89, 545.77, 735.74, 567.01, 381.54, 757.88, 581.51, 424.9, 782.14, 596.31, 446.74, 808.15, 611.57, 464.4, 836.68, 627.34, 480.43, 869.21, 643.61, 495.43, 907.67, 660.35, 509.92, 955.76, 677.59, 524.18, 1021.11, 695.62, 538.53, 1154.84, 715.01, 552.79],
            "End Mass [m/z]":[736.24, 567.5, 382.04, 758.38, 582.01, 425.4, 782.64, 596.81, 447.23, 808.65, 612.07, 464.9, 837.18, 627.84, 480.93, 869.71, 644.1, 495.93, 908.17, 660.85, 510.43, 956.26, 678.09, 524.68, 1021.61, 696.12, 539.03, 1155.34, 715.51, 553.28, 746.84, 574.71, 412.89, 769.91, 589.31, 437.92, 795.37, 604.3, 456.55, 821.93, 619.83, 473.26, 852.43, 635.85, 488.6, 886.99, 652.36, 503.27, 929.36, 669.33, 517.58, 983.17, 686.85, 531.79, 1060.04, 705.39, 546.27, 1250.64, 725.63, 560.3],
            "CE [eV]":['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'],
            "W":[11.110000000000014, 7.7000000000000455, 31.360000000000014, 12.039999999999964, 7.7999999999999545, 13.009999999999991, 13.230000000000018, 8.0, 9.810000000000002, 13.779999999999973, 8.270000000000095, 8.849999999999966, 15.75, 8.509999999999991, 8.170000000000016, 17.780000000000086, 8.75, 7.829999999999984, 21.67999999999995, 8.990000000000009, 7.660000000000025, 27.399999999999977, 9.259999999999991, 7.599999999999909, 38.940000000000055, 9.769999999999982, 7.740000000000009, 95.79999999999995, 10.620000000000005, 7.509999999999991, 11.100000000000023, 7.7000000000000455, 31.349999999999966, 12.029999999999973, 7.7999999999999545, 13.020000000000039, 13.230000000000018, 7.990000000000009, 9.810000000000002, 13.779999999999973, 8.259999999999991, 8.860000000000014, 15.75, 8.509999999999991, 8.170000000000016, 17.779999999999973, 8.75, 7.839999999999975, 21.690000000000055, 8.980000000000018, 7.660000000000025, 27.409999999999968, 9.259999999999991, 7.610000000000014, 38.92999999999995, 9.769999999999982, 7.740000000000009, 95.80000000000018, 10.620000000000005, 7.509999999999991],
            "H":[0.15500000000000014, 0.15999999999999992, 0.20500000000000007, 0.17299999999999993, 0.10699999999999998, 0.27, 0.20399999999999996, 0.09599999999999997, 0.29000000000000004, 0.235, 0.09499999999999997, 0.30000000000000004, 0.264, 0.09999999999999998, 0.30600000000000005, 0.28500000000000014, 0.11499999999999988, 0.31000000000000005, 0.30500000000000016, 0.1279999999999999, 0.31700000000000006, 0.32599999999999985, 0.137, 0.32700000000000007, 0.345, 0.14500000000000002, 0.33999999999999997, 0.345, 0.15000000000000002, 0.355, 0.15999999999999992, 0.12, 0.25, 0.18799999999999994, 0.09799999999999998, 0.28400000000000003, 0.21999999999999997, 0.09499999999999997, 0.29500000000000004, 0.25, 0.09699999999999998, 0.30300000000000005, 0.27500000000000013, 0.10699999999999987, 0.30800000000000005, 0.29600000000000004, 0.12, 0.31400000000000006, 0.31600000000000006, 0.134, 0.32000000000000006, 0.33499999999999996, 0.1409999999999999, 0.3340000000000001, 0.345, 0.14800000000000002, 0.347, 0.33999999999999986, 0.15000000000000013, 0.36],
            "xy":[(725.13, 0.965), (559.8, 0.805), (350.68, 0.6), (746.34, 0.977), (574.21, 0.87), (412.39, 0.6), (769.41, 0.986), (588.81, 0.89), (437.42, 0.6), (794.87, 0.995), (603.8, 0.9), (456.05, 0.6), (821.43, 1.006), (619.33, 0.906), (472.76, 0.6), (851.93, 1.025), (635.35, 0.91), (488.1, 0.6), (886.49, 1.045), (651.86, 0.917), (502.77, 0.6), (928.86, 1.064), (668.83, 0.927), (517.08, 0.6), (982.67, 1.085), (686.35, 0.94), (531.29, 0.6), (1059.54, 1.105), (704.89, 0.955), (545.77, 0.6), (735.74, 0.97), (567.01, 0.85), (381.54, 0.6), (757.88, 0.982), (581.51, 0.884), (424.9, 0.6), (782.14, 0.99), (596.31, 0.895), (446.74, 0.6), (808.15, 1.0), (611.57, 0.903), (464.4, 0.6), (836.68, 1.015), (627.34, 0.908), (480.43, 0.6), (869.21, 1.034), (643.61, 0.914), (495.43, 0.6), (907.67, 1.054), (660.35, 0.92), (509.92, 0.6), (955.76, 1.075), (677.59, 0.934), (524.18, 0.6), (1021.11, 1.095), (695.62, 0.947), (538.53, 0.6), (1154.84, 1.11), (715.01, 0.96), (552.79, 0.6)]
        })
        return lubeckdia
    #phospho DIA windows
    def phosphodiawindow():
        phosphodia=pd.DataFrame({
            "#MS Type":['PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF', 'PASEF'],
            "Cycle Id":[1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            "Start IM [1/K0]":[0.8691, 0.6811, 0.8834, 0.691, 0.912, 0.701, 0.9264, 0.7109, 0.9407, 0.7208, 0.9694, 0.7308, 0.9837, 0.7407, 1.0123, 0.7544, 1.0267, 0.7688, 0.7831, 0.7974, 0.8117, 0.8261, 0.8404, 0.8547, 0.8977, 0.955, 0.998, 1.041],
            "End IM [1/K0]":[1.1616, 0.8579, 1.1791, 0.8786, 1.2142, 0.8993, 1.2317, 0.92, 1.2492, 0.9407, 1.2842, 0.9614, 1.3017, 0.9821, 1.3368, 1.0028, 1.3543, 1.0235, 1.0442, 1.0649, 1.0856, 1.1063, 1.1266, 1.1441, 1.1966, 1.2667, 1.3192, 1.3718],
            "Start Mass [m/z]":[839.43, 419.43, 867.43, 447.43, 923.43, 475.43, 951.43, 503.43, 979.43, 531.43, 1035.43, 559.43, 1063.43, 587.43, 1119.43, 615.43, 1147.43, 643.43, 671.43, 699.43, 727.43, 755.43, 783.43, 811.43, 895.43, 1007.43, 1091.43, 1175.43],
            "End Mass [m/z]":[867.43, 447.43, 895.43, 475.43, 951.43, 503.43, 979.43, 531.43, 1007.43, 559.43, 1063.43, 587.43, 1091.43, 615.43, 1147.43, 643.43, 1175.43, 671.43, 699.43, 727.43, 755.43, 783.43, 811.43, 839.43, 923.43, 1035.43, 1119.43, 1203.43],
            "CE [eV]":['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'],
            "W":[28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 27.999999999999943, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.0, 28.000000000000114, 28.0, 28.0],
            "H":[0.2925, 0.17679999999999996, 0.2957000000000001, 0.1876000000000001, 0.3021999999999999, 0.19830000000000003, 0.3053, 0.20910000000000006, 0.3085000000000001, 0.21989999999999998, 0.31479999999999997, 0.23060000000000003, 0.31800000000000006, 0.24139999999999995, 0.3245, 0.24839999999999995, 0.3276000000000001, 0.25470000000000004, 0.2611, 0.26749999999999996, 0.2738999999999999, 0.2802000000000001, 0.2862, 0.2893999999999999, 0.29890000000000005, 0.3117, 0.32119999999999993, 0.3308],
            "xy":[(839.43, 0.8691), (419.43, 0.6811), (867.43, 0.8834), (447.43, 0.691), (923.43, 0.912), (475.43, 0.701), (951.43, 0.9264), (503.43, 0.7109), (979.43, 0.9407), (531.43, 0.7208), (1035.43, 0.9694), (559.43, 0.7308), (1063.43, 0.9837), (587.43, 0.7407), (1119.43, 1.0123), (615.43, 0.7544), (1147.43, 1.0267), (643.43, 0.7688), (671.43, 0.7831), (699.43, 0.7974), (727.43, 0.8117), (755.43, 0.8261), (783.43, 0.8404), (811.43, 0.8547), (895.43, 0.8977), (1007.43, 0.955), (1091.43, 0.998), (1175.43, 1.041)],
        })
        return phosphodia

    #render ui call for dropdown calling charge states that were detected
    @render.ui
    def chargestates_chargeptmheatmap_ui():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        mincharge=min(searchoutput["FG.Charge"])
        maxcharge=max(searchoutput["FG.Charge"])
        opts=[item for item in range(mincharge,maxcharge+1)]
        opts.insert(0,0)
        return ui.input_selectize("chargestates_chargeptmheatmap_list","Pick charge to plot data for (use 0 for all):",choices=opts)
    #render ui call for dropdown calling PTMs that were detected
    @render.ui
    def ptm_chargeptmheatmap_ui():
        listofptms=find_ptms()
        ptmshortened=[]
        for i in range(len(listofptms)):
            ptmshortened.append(re.sub(r'\(.*?\)',"",listofptms[i]))
        ptmdict={ptmshortened[i]: listofptms[i] for i in range(len(listofptms))}
        nonedict={"None":"None"}
        ptmdict=(nonedict | ptmdict)
        return ui.input_selectize("ptm_chargeptmheatmap_list","Pick PTM to plot data for (use None for all precursors):",choices=ptmdict,selected="None")

    #Charge/PTM precursor heatmap
    @render.plot(width=1000,height=500)
    def chargeptmheatmap():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

        charge=input.chargestates_chargeptmheatmap_list()
        ptm=input.ptm_chargeptmheatmap_list()
        numbins_x=input.chargeptm_numbins_x()
        numbins_y=input.chargeptm_numbins_y()
        numbins=[numbins_x,numbins_y]
        cmap=matplotlib.colors.LinearSegmentedColormap.from_list("",["white","blue","red"])
        figsize=(8,6)

        fig,ax=plt.subplots(figsize=figsize)

        if ptm=="None":
            if charge=="0":
                #all precursors
                his2dsample=searchoutput[["R.Condition","R.Replicate","EG.IonMobility","FG.PrecMz"]]
                title="m/z vs Mobility, Precursor IDs"
                savetitle="All Precursor IDs Heatmap_"
            elif charge!="0":
                #all precursors of specific charge
                his2dsample=searchoutput[searchoutput["FG.Charge"]==int(charge)][["R.Condition","R.Replicate","EG.IonMobility","FG.PrecMz"]]
                title="m/z vs Mobility, "+str(charge)+"+ Precursor IDs"
                savetitle=str(charge)+"+_"+"_Precursor IDs Heatmap_"   
        if ptm!="None":
            if charge=="0":
                #all modified precursors 
                his2dsample=searchoutput[searchoutput["EG.ModifiedPeptide"].str.contains(ptm)][["R.Condition","R.Replicate","EG.IonMobility","FG.PrecMz"]]
                title="m/z vs Mobility, "+ptm+" Precursor IDs"
                savetitle=ptm+"_Precursor IDs Heatmap_"                    
            elif charge!="0":
                #modified precursors of specific charge
                his2dsample=searchoutput[(searchoutput["FG.Charge"]==int(charge))&(searchoutput["EG.ModifiedPeptide"].str.contains(ptm))][["R.Condition","R.Replicate","EG.IonMobility","FG.PrecMz"]]
                title="m/z vs Mobility, "+ptm+" "+str(charge)+"+ Precursor IDs"
                savetitle=ptm+"_"+str(charge)+"+_"+"_Precursor IDs Heatmap_"
        j=ax.hist2d(his2dsample["FG.PrecMz"],his2dsample["EG.IonMobility"],bins=numbins,cmap=cmap)
        ax.set_title(title)
        ax.set_xlabel("m/z")
        ax.set_ylabel("Ion Mobility ($1/K_{0}$)")
        fig.colorbar(j[3],ax=ax)

        ax.set_ylim(0.6,1.45)
        ax.set_xlim(100,1700)
        
        fig.set_tight_layout(True)
        
        if input.windows_choice()!="None":
            if input.windows_choice()=="lubeck":
                diawindows=lubeckdiawindow()
            elif input.windows_choice()=="phospho":
                diawindows=phosphodiawindow()
            elif input.windows_choice()=="imported":
                diawindows=diawindows_import()

            for i in range(len(diawindows)):
                rect=matplotlib.patches.Rectangle(xy=diawindows["xy"][i],width=diawindows["W"][i],height=diawindows["H"][i],facecolor="red",alpha=0.1,edgecolor="grey")
                ax.add_patch(rect) 
        
        return fig

    @render.ui
    def cond_rep_list_venn1():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        opts=resultdf["Cond_Rep"].tolist()
        return ui.input_selectize("cond_rep1","Pick first run to compare:",choices=opts)
    @render.ui
    def cond_rep_list_venn2():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        opts=resultdf["Cond_Rep"].tolist()
        return ui.input_selectize("cond_rep2","Pick second run to compare:",choices=opts)

    @render.ui
    def binslider_ui():
        return ui.input_slider("binslider","Number of RT bins:",min=100,max=1000,step=50,value=500,ticks=True)

    #plot # of IDs vs RT for each run
    @reactive.effect
    def _():
        @render.plot(width=input.idsvsrt_width(),height=input.idsvsrt_height())
        def ids_vs_rt():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            
            rtmax=float(math.ceil(max(searchoutput["EG.ApexRT"])/10)*10) #needs to be a float
            numbins=input.binslider()

            bintime=rtmax/numbins*60

            axisfont=15

            fig,ax=plt.subplots()

            for i in sampleconditions:
                for k in range(max(maxreplicatelist)+1):
                    run=searchoutput[searchoutput["R.Condition"].str.contains(i)&(searchoutput["R.Replicate"]==k)]["EG.ApexRT"]
                    if run.empty:
                        continue
                    hist=np.histogram(run,bins=numbins,range=(0.0,rtmax))
                    ax.plot(np.delete(hist[1],0),hist[0],linewidth=0.5,label=i+"_"+str(k))

            ax.set_ylabel("# of IDs",fontsize=axisfont)
            ax.set_xlabel("RT (min)",fontsize=axisfont)
            ax.tick_params(axis="both",labelsize=axisfont)
            ax.text(0,(ax.get_ylim()[1]-(0.1*ax.get_ylim()[1])),"~"+str(round(bintime,2))+" s per bin",fontsize=axisfont)
            legend=ax.legend(loc='center left', bbox_to_anchor=(1, 0.5),prop={'size':10})
            for i in legend.legend_handles:
                i.set_linewidth(5)
            ax.set_axisbelow(True)
            ax.grid(linestyle="--")
            ax.set_title("# of IDs vs RT")
            return fig
    
    #plot venn diagram comparing IDs between runs
    @render.plot
    def venndiagram():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

        pickA=input.cond_rep1()
        pickB=input.cond_rep2()
        vennpick=input.vennpick()

        conditionA=searchoutput[searchoutput["Cond_Rep"].str.contains(pickA)][["PG.ProteinNames","FG.Charge","PEP.StrippedSequence","EG.ModifiedPeptide"]]
        conditionB=searchoutput[searchoutput["Cond_Rep"].str.contains(pickB)][["PG.ProteinNames","FG.Charge","PEP.StrippedSequence","EG.ModifiedPeptide"]]

        if vennpick=="proteins":
            AvsB=conditionA["PG.ProteinNames"].drop_duplicates().reset_index(drop=True).isin(conditionB["PG.ProteinNames"].drop_duplicates().reset_index(drop=True)).tolist()
            BvsA=conditionB["PG.ProteinNames"].drop_duplicates().reset_index(drop=True).isin(conditionA["PG.ProteinNames"].drop_duplicates().reset_index(drop=True)).tolist()
        elif vennpick=="peptides":
            AvsB=conditionA["EG.ModifiedPeptide"].drop_duplicates().reset_index(drop=True).isin(conditionB["EG.ModifiedPeptide"].drop_duplicates().reset_index(drop=True)).tolist()
            BvsA=conditionB["EG.ModifiedPeptide"].drop_duplicates().reset_index(drop=True).isin(conditionA["EG.ModifiedPeptide"].drop_duplicates().reset_index(drop=True)).tolist()
        elif vennpick=="precursors":
            AvsB=conditionA["EG.ModifiedPeptide"].isin(conditionB["EG.ModifiedPeptide"].drop_duplicates()).tolist()
            BvsA=conditionB["EG.ModifiedPeptide"].isin(conditionA["EG.ModifiedPeptide"].drop_duplicates()).tolist()

        AnotB=sum(1 for i in AvsB if i==False)
        BnotA=sum(1 for i in BvsA if i==False)
        bothAB=sum(1 for i in AvsB if i==True)
        vennlist=[AnotB,BnotA,bothAB]

        fig,ax=plt.subplots()
        venn2(subsets=vennlist,set_labels=(pickA,pickB),set_colors=("tab:blue","tab:orange"),ax=ax)
        venn2_circles(subsets=vennlist,linestyle="dashed",linewidth=0.5)
        plt.title("Venn Diagram for "+vennpick)
        return fig

#endregion

# ============================================================================= Mixed Proteome
#region

    @render.text
    def organisminput_readout():
        return input.organisminput()

    @render.text
    def referenceratio_readout():
        return input.referenceratio()
    
    @render.text
    def testratio_readout():
        return input.testratio()

    #plot summed intensities for each organism
    @reactive.effect
    def _():
        @render.plot(width=input.summedintensities_width(),height=input.summedintensities_height())
        def summedintensities():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            organismlist=list(input.organisminput().split(" "))

            for i in organismlist:
                exec(f'dict_{i}=dict()')
                for j in sampleconditions:
                    for k in range(max(maxreplicatelist)+1):
                        replicatedata=searchoutput[searchoutput["R.Condition"].str.contains(j)&(searchoutput["R.Replicate"]==k)]
                        if replicatedata.empty:
                            continue
                        exec(f'dict_{i}["{j}_{k}"]=replicatedata[["PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates().reset_index(drop=True)')
                        exec(f'dict_{i}["{j}_{k}"]=dict_{i}["{j}_{k}"][dict_{i}["{j}_{k}"]["PG.ProteinNames"].str.contains(i)&(dict_{i}["{j}_{k}"]["PG.MS2Quantity"]>0)].reset_index(drop=True)')

            samplekeys=resultdf["Cond_Rep"].tolist()
            intensitysumdf=pd.DataFrame(index=samplekeys)
            for i in organismlist:
                exec(f'organismdict=dict_{i}')
                exec(f'intensitylist_{i}=[]')
                for condition in samplekeys:
                    exec(f'intensitylist_{i}.append(dict_{i}[condition]["PG.MS2Quantity"].sum())')
                exec(f'intensitysumdf[i]=intensitylist_{i}')
            
            figsize=(5,5)
            titlefont=20
            axisfont=15

            matplottabcolors=list(mcolors.TABLEAU_COLORS)
            bluegray_colors=["#054169","#0071BC","#737373"]

            if input.coloroptions_sumint()=="matplot":
                colors=matplottabcolors
            elif input.coloroptions_sumint()=="bluegray":
                colors=bluegray_colors

            x=np.arange(len(intensitysumdf.index))
            fig,ax=plt.subplots(figsize=figsize)
            ax.bar(x,intensitysumdf[organismlist[0]],label=organismlist[0],color=colors[0])
            ax.bar(x,intensitysumdf[organismlist[1]],bottom=intensitysumdf[organismlist[0]],label=organismlist[1],color=colors[1])
            ax.bar(x,intensitysumdf[organismlist[2]],bottom=intensitysumdf[organismlist[0]]+intensitysumdf[organismlist[1]],label=organismlist[2],color=colors[2])

            ax.set_xticks(x,labels=intensitysumdf.index,rotation=90,fontsize=axisfont)
            ax.tick_params(axis="y",labelsize=axisfont)
            ax.set_ylabel("Total Intensity",fontsize=axisfont)
            ax.legend(loc="center left",bbox_to_anchor=(1, 0.5),fontsize=axisfont)
            ax.set_axisbelow(True)
            ax.grid(linestyle="--")
            ax.set_title("Total Intensity per Organism per Run",fontsize=titlefont)
            return fig

    #plot protein counts per organism
    @reactive.effect
    def _():
        @render.plot(width=input.countsperorganism_width(),height=input.countsperorganism_height())
        def countsperorganism():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()
            organismlist=list(input.organisminput().split(" "))
            
            for i in organismlist:
                exec(f'dict_{i}=dict()')
                for j in sampleconditions:
                    for k in range(max(maxreplicatelist)+1):
                        replicatedata=searchoutput[searchoutput["R.Condition"].str.contains(j)&(searchoutput["R.Replicate"]==k)]
                        if replicatedata.empty:
                            continue
                        exec(f'dict_{i}["{j}_{k}"]=replicatedata[["PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates().reset_index(drop=True)')
                        exec(f'dict_{i}["{j}_{k}"]=dict_{i}["{j}_{k}"][dict_{i}["{j}_{k}"]["PG.ProteinNames"].str.contains(i)&(dict_{i}["{j}_{k}"]["PG.MS2Quantity"]>0)].reset_index(drop=True)')

            samplekeys=resultdf["Cond_Rep"].tolist()

            proteincountdf=pd.DataFrame(index=samplekeys)
            for i in organismlist:
                exec(f'organismdict=dict_{i}')
                exec(f'list_{i}=[]')
                for condition in samplekeys:
                    exec(f'list_{i}.append(len(organismdict[condition]))')
                exec(f'proteincountdf[i]=list_{i}')

            figsize=(10,5)
            titlefont=20
            axisfont=15
            labelfont=15
            y_padding=0.25

            matplottabcolors=list(mcolors.TABLEAU_COLORS)
            bluegray_colors=["#054169","#0071BC","#737373"]

            if input.coloroptions_sumint()=="matplot":
                colors=matplottabcolors
            elif input.coloroptions_sumint()=="bluegray":
                colors=bluegray_colors

            n=len(samplekeys)
            x=np.arange(n)
            width=0.25

            fig,ax=plt.subplots(figsize=figsize)
            for i in range(len(organismlist)):
                ax.bar(x+(i*width),proteincountdf[organismlist[i]],width=width,label=organismlist[i],color=colors[i])
                ax.bar_label(ax.containers[i],label_type="edge",rotation=90,padding=5,fontsize=14)

            ax.set_xticks(x+width,samplekeys,rotation=90)
            ax.tick_params(axis='both',labelsize=14)
            ax.set_ylim(top=max(proteincountdf[organismlist[0]])+(y_padding)*max(proteincountdf[organismlist[0]]))
            ax.set_axisbelow(True)
            ax.grid(linestyle="--")
            ax.legend(loc='center left', bbox_to_anchor=(1, 0.5),prop={'size':axisfont})
            ax.set_ylabel("Counts",fontsize=14)   
            ax.set_title("Protein Counts per Organism")              
            return fig

    #render ui call for dropdown calling sample condition names
    @render.ui
    def referencecondition():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        opts=sampleconditions
        return ui.input_selectize("referencecondition_list","Pick reference condition:",choices=opts,selected=opts[0])
    #render ui call for dropdown calling sample condition names
    @render.ui
    def testcondition():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        opts=sampleconditions
        return ui.input_selectize("testcondition_list","Pick test condition:",choices=opts,selected=opts[1])
    @render.text
    def organismreminder():
        return "Organisms in order: "+input.organisminput()

    #plot quant ratios for each organism
    @render.plot(width=1200,height=600)
    def quantratios():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        colorblocks,colors,matplottabcolors,tabcolorsblocks=colordfs()

        organismlist=list(input.organisminput().split(" "))

        control=input.referencecondition_list()
        test=input.testcondition_list()
        
        referenceratios=[int(x) for x in input.referenceratio().split()]
        testratios=[int(x) for x in input.testratio().split()]
        expectedratios=[]
        for i in range(len(referenceratios)):
            expectedratios.append(np.log2(testratios[i]/referenceratios[i]))

        figsize=(10,5)
        titlefont=20
        axisfont=15
        labelfont=15
        y_padding=0.2

        matplottabcolors=list(mcolors.TABLEAU_COLORS)
        bluegray_colors=["#054169","#0071BC","#737373"]

        if input.coloroptions_sumint()=="matplot":
            colors=matplottabcolors
        elif input.coloroptions_sumint()=="bluegray":
            colors=bluegray_colors

        cvcutoff=input.cvcutofflevel()

        for i in organismlist:
            exec(f'dict_{i}=dict()')
            for j in sampleconditions:
                for k in range(max(maxreplicatelist)+1):
                    replicatedata=searchoutput[searchoutput["R.Condition"].str.contains(j)&(searchoutput["R.Replicate"]==k)]
                    if replicatedata.empty:
                        continue
                    exec(f'dict_{i}["{j}_{k}"]=replicatedata[["PG.ProteinNames","PG.MS2Quantity"]].drop_duplicates().reset_index(drop=True)')
                    exec(f'dict_{i}["{j}_{k}"]=dict_{i}["{j}_{k}"][dict_{i}["{j}_{k}"]["PG.ProteinNames"].str.contains(i)&(dict_{i}["{j}_{k}"]["PG.MS2Quantity"]>0)].reset_index(drop=True)')

        for organism in organismlist:
            listofdfs=[]
            for condition in sampleconditions:
                tempdfs=[]
                for replicate in range(max(maxreplicatelist)+1):
                    if replicate==0:
                        continue
                    exec(f'tempdf_{replicate}=dict_{organism}["{condition}_{replicate}"].set_index("PG.ProteinNames")')
                    exec(f'tempdfs.append(tempdf_{replicate})')
                exec(f'listofdfs.append(pd.concat(tempdfs,axis=1,join="outer").loc[:,["PG.MS2Quantity"]].mean(axis=1))')
            exec(f'df_{organism}=pd.concat(listofdfs,axis=1)')
            exec(f'df_{organism}.columns=sampleconditions')

        for organism in organismlist:
            listofdfs=[]
            for condition in sampleconditions:
                tempdfs=[]
                for replicate in range(max(maxreplicatelist)+1):
                    if replicate==0:
                        continue
                    exec(f'tempdf_{replicate}=dict_{organism}["{condition}_{replicate}"].set_index("PG.ProteinNames")')
                    exec(f'tempdfs.append(tempdf_{replicate})')
                exec(f'listofdfs.append(pd.concat(tempdfs,axis=1,join="outer").loc[:,["PG.MS2Quantity"]].std(axis=1))')
            exec(f'df_{organism}_stdev=pd.concat(listofdfs,axis=1)')
            exec(f'df_{organism}_stdev.columns=sampleconditions')
            
        for organism in organismlist:
            for condition in sampleconditions:
                exec(f'df_{organism}["{condition}_CV"]=df_{organism}_stdev["{condition}"]/df_{organism}["{condition}"]*100')

        if input.cvcutoff_switch()==True:
            for organism in organismlist:
                exec(f'df_{organism}.drop(df_{organism}[(df_{organism}[test+"_CV"]>cvcutoff) | (df_{organism}[test+"_CV"]>cvcutoff)].index,inplace=True)')

        organismratioaverage=[]
        organismratiostdev=[]
        for organism in organismlist:
            exec(f'merged_{organism}=df_{organism}[test].reset_index().dropna().merge(df_{organism}[control].reset_index().dropna(),how="inner")')
            exec(f'log2ratio_{organism}=np.log2(merged_{organism}[test]/merged_{organism}[control])')
            exec(f'merged_log10_{organism}=np.log10(merged_{organism}[[test,control]])')
            exec(f'experimentalratio_{organism}=np.average(log2ratio_{organism})')
            
            exec(f'organismratioaverage.append(np.mean(log2ratio_{organism}))')
            exec(f'organismratiostdev.append(np.std(log2ratio_{organism}))')

        fig,ax=plt.subplots(nrows=1,ncols=3,figsize=figsize,gridspec_kw={"width_ratios":[2,5,2]})

        x=0
        for organism in organismlist:
            exec(f'ax[0].bar(x,len(merged_{organism}),color=colors[x])')
            ax[0].bar_label(ax[0].containers[x],label_type="edge",rotation=90,padding=5,fontsize=labelfont)
            exec(f'ax[1].scatter(merged_log10_{organism}[control],log2ratio_{organism},alpha=0.25,color=colors[x])')
            exec(f'ax[2].hist(log2ratio_{organism},bins=100,orientation=u"horizontal",alpha=0.5,density=True,color=colors[x])')
            x=x+1

        ax[0].set_xticks(np.arange(len(organismlist)),organismlist,rotation=90)
        ax[0].set_ylabel("Number of Proteins",fontsize=axisfont)
        bottom,top=ax[0].get_ylim()
        ax[0].set_ylim(top=top+(y_padding*top))
        ax[0].tick_params(axis="both",labelsize=axisfont)

        leg=ax[1].legend(organismlist,loc="upper right")
        for tag in leg.legend_handles:
            tag.set_alpha(1)
        ax[1].set_xlabel("log10 Intensity, Reference",fontsize=axisfont)
        ax[1].set_ylabel("log2 Ratio, Test/Reference",fontsize=axisfont)
        ax[1].set_title("Reference: "+control+", Test: "+test,pad=10,fontsize=titlefont)
        ax[1].tick_params(axis="both",labelsize=axisfont)

        ax[2].set_xlabel("Density",fontsize=axisfont)
        ax[2].set_ylabel("log2 Ratio, Test/Reference",fontsize=axisfont)
        ax[2].tick_params(axis="both",labelsize=axisfont)

        if input.plotrange_switch()==True:
            ymin=input.plotrange()[0]
            ymax=input.plotrange()[1]
            ax[1].set_ylim(ymin,ymax)
            ax[2].set_ylim(ymin,ymax)
        
        for i in range(3):  
            ax[i].set_axisbelow(True)
            ax[i].grid(linestyle="--")

        for i in range(len(expectedratios)):
            ax[1].axhline(y=expectedratios[i],color=colors[i])
            ax[2].axhline(y=expectedratios[i],color=colors[i])

        for i in range(len(organismratioaverage)):
            ax[1].axhline(y=organismratioaverage[i],color=colors[i],linestyle="dashed")
            ax[2].axhline(y=organismratioaverage[i],color=colors[i],linestyle="dashed")
            
        fig.set_tight_layout(True)

#endregion

# ============================================================================= PRM
#region

    #import prm list and generate a searchoutput-like table for just the prm peptides
    @reactive.calc
    def prm_import():
        if input.prm_list() is None:
            return pd.DataFrame()
        prm_list=pd.read_csv(input.prm_list()[0]["datapath"])
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        df_list=[]
        for peptide in prm_list["EG.ModifiedPeptide"]:
            prm_peptide=searchoutput[searchoutput["EG.ModifiedPeptide"]==peptide]
            df_list.append(prm_peptide)
        searchoutput_prmpepts=pd.concat(df_list).reset_index(drop=True)
        if "Concentration" in searchoutput.columns:
            searchoutput_prmpepts.sort_values("Concentration")
        return prm_list,searchoutput_prmpepts

    #prm selectize peptide list
    @render.ui
    def prmpeptracker_pick():
        prm_list,searchoutput_prmpepts=prm_import()
        opts=prm_list["EG.ModifiedPeptide"]
        return ui.input_selectize("prmpeptracker_picklist","Pick PRM peptide to plot data for:",choices=opts,width="600px")

    #plot intensity across runs, number of replicates, and CVs of selected peptide from prm list
    @reactive.effect
    def _():
        @render.plot(width=input.prmpeptracker_width(),height=input.prmpeptracker_height())
        def prmpeptracker_plot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            prm_list,searchoutput_prmpepts=prm_import()

            peplist=prm_list["EG.ModifiedPeptide"]
            peptide=peplist[int(input.prmpeptracker_picklist())]

            pepdf=searchoutput_prmpepts[searchoutput_prmpepts["EG.ModifiedPeptide"]==peptide]
            chargelist=pepdf["FG.Charge"].drop_duplicates().tolist()

            fig,ax=plt.subplots(ncols=2,nrows=2)
            for i,charge in enumerate(chargelist):
                meandf=pepdf[pepdf["FG.Charge"]==charge][["R.Condition","FG.MS2Quantity"]].groupby("R.Condition").mean()
                stdev=pepdf[pepdf["FG.Charge"]==charge][["R.Condition","FG.MS2Quantity"]].groupby("R.Condition").std()
                cv=stdev/meandf*100
                meandf=meandf.reset_index()
                stdev=stdev.reset_index()
                cv=cv.reset_index()
                x=np.arange(0,len(meandf["R.Condition"]),1)
                y=meandf["FG.MS2Quantity"].tolist()
                fit=np.poly1d(np.polyfit(x,y,1))
                ax[0,0].errorbar(x,y,yerr=stdev["FG.MS2Quantity"],marker="o",linestyle="None")
                ax[0,0].plot(x,fit(x),linestyle="--",color="black")
                ax[0,0].set_ylabel("FG.MS2Quantity")
                
                width=0.25
                detectedinreps=pepdf[pepdf["FG.Charge"]==charge].groupby("R.Condition").size().tolist()
                ax[0,1].bar(x+i*width,detectedinreps,width=width,label=str(charge)+"+")
                ax[0,1].set_xticks(x+(width/len(meandf["R.Condition"])),meandf["R.Condition"])
                ax[0,1].set_ylabel("Number of Replicates")

                ax[1,0].plot(meandf["R.Condition"],cv["FG.MS2Quantity"],marker="o")
                ax[1,0].axhline(y=20,linestyle="--",color="black")
                ax[1,0].set_ylabel("CV (%)")
                
                if "Concentration" in searchoutput.columns:
                    concentrationlist=pepdf[pepdf["FG.Charge"]==charge]["Concentration"].tolist()
                    expectratio=[]
                    for conc in concentrationlist:
                        conc_min=min(concentrationlist)
                        expectratio.append(conc/conc_min)

                    measuredratio=[]
                    signallist=pepdf[pepdf["FG.Charge"]==charge]["FG.MS2Quantity"]
                    for signal in signallist:
                        conc_min=min(signallist)
                        measuredratio.append(signal/conc_min)
                    ax[1,1].scatter(expectratio,measuredratio)
                    ax[1,1].set_xlabel("Expected Ratio")
                    ax[1,1].set_ylabel("Measured Ratio")
                else:
                    ax[1,1].set_visible(False)

            ax[0,0].set_title("Intensity Across Runs")
            ax[0,0].set_axisbelow(True)
            ax[0,0].grid(linestyle="--")

            ax[0,1].set_title("Number of Replicates Observed")
            ax[0,1].set_axisbelow(True)
            ax[0,1].grid(linestyle="--")

            ax[1,0].set_title("CVs")
            ax[1,0].set_axisbelow(True)
            ax[1,0].grid(linestyle="--")

            ax[1,1].set_title("Dilution Curve")
            ax[1,1].set_axisbelow(True)
            ax[1,1].grid(linestyle="--")

            fig.legend(loc="lower right",bbox_to_anchor=(0.99,0.9))
            fig.suptitle(peptide.strip("_"))
            fig.set_tight_layout(True)

    #plot intensity of all prm peptides across runs
    @reactive.effect
    def _():
        @render.plot(width=input.prmpepintensity_width(),height=input.prmpepintensity_height())
        def prmpepintensity_plot():
            searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
            prm_list,searchoutput_prmpepts=prm_import()

            df_list=[]
            for peptide in prm_list["EG.ModifiedPeptide"]:
                prm_peptide=searchoutput[searchoutput["EG.ModifiedPeptide"]==peptide]
                df_list.append(prm_peptide)
            searchoutput_prmpepts=pd.concat(df_list).reset_index(drop=True)

            fig,ax=plt.subplots()
            for peptide in prm_list["EG.ModifiedPeptide"]:
                pepdf=searchoutput_prmpepts[searchoutput_prmpepts["EG.ModifiedPeptide"]==peptide]
                chargelist=pepdf["FG.Charge"].drop_duplicates().tolist()
                for charge in chargelist:
                    ax.plot(pepdf[pepdf["FG.Charge"]==charge]["Cond_Rep"],np.log10(pepdf[pepdf["FG.Charge"]==charge]["FG.MS2Quantity"]),marker="o",label=peptide.strip("_")+"_"+str(charge)+"+")
            ax.legend(loc='center left', bbox_to_anchor=(1,0.5),prop={'size':8})
            ax.tick_params(axis="x",rotation=90)
            ax.set_xlabel("Condition")
            ax.set_ylabel("log10(FG.MS2Quantity)")
            ax.set_axisbelow(True)
            ax.grid(linestyle="--")

    #generate prm table to be exported to timscontrol
    @reactive.calc
    def prm_list_import():
        if input.prm_list() is None:
            return pd.DataFrame()
        prm_list=pd.read_csv(input.prm_list()[0]["datapath"])
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        try:
            isolationwidth=float(input.isolationwidth_input())
        except:
            isolationwidth=0
        try:
            rtwindow=float(input.rtwindow_input())
        except:
            rtwindow=0
        try:
            imwindow=float(input.imwindow_input())
        except:
            imwindow=0
        df_list=[]
        for peptide in prm_list["EG.ModifiedPeptide"]:
            prm_peptide=searchoutput[searchoutput["EG.ModifiedPeptide"]==peptide][["PG.ProteinNames","EG.ModifiedPeptide","FG.PrecMz","FG.Charge","EG.ApexRT","EG.IonMobility"]].groupby(["PG.ProteinNames","EG.ModifiedPeptide","FG.Charge"]).mean().reset_index()
            df_list.append(prm_peptide)
        searchoutput_prm=pd.concat(df_list).reset_index(drop=True)
        searchoutput_prm["EG.ApexRT"]=searchoutput_prm["EG.ApexRT"]*60

        searchoutput_prm.rename(columns={"FG.PrecMz":"Mass [m/z]","FG.Charge":"Charge","EG.ApexRT":"RT [s]"},inplace=True)

        mzisolationwidth=[]
        RTrange=[]
        startIM=[]
        endIM=[]
        CE=[]
        externalID=[]
        description=[]
        for i in range(len(searchoutput_prm)):
            mzisolationwidth.append(isolationwidth)
            RTrange.append(rtwindow)
            startIM.append(searchoutput_prm["EG.IonMobility"][i]-imwindow)
            endIM.append(searchoutput_prm["EG.IonMobility"][i]+imwindow)
            CE.append("")
            externalID.append(searchoutput_prm["EG.ModifiedPeptide"][i])
            description.append("")

        searchoutput_prm["Isolation Width [m/z]"]=mzisolationwidth
        searchoutput_prm["RT Range [s]"]=RTrange
        searchoutput_prm["Start IM [1/k0]"]=startIM
        searchoutput_prm["End IM [1/k0]"]=endIM
        searchoutput_prm["CE [eV]"]=CE
        searchoutput_prm["External ID"]=externalID
        searchoutput_prm["Description"]=description

        searchoutput_prm=searchoutput_prm[["Mass [m/z]","Charge","Isolation Width [m/z]","RT [s]","RT Range [s]","Start IM [1/k0]","End IM [1/k0]","CE [eV]","External ID","Description","PG.ProteinNames","EG.ModifiedPeptide","EG.IonMobility"]]

        searchoutput_prm.drop(columns=["PG.ProteinNames","EG.ModifiedPeptide","EG.IonMobility"],inplace=True)

        return searchoutput_prm
    
    #show prm list in window
    @render.data_frame
    def prm_table():
        searchoutput_prm=prm_list_import()
        return render.DataGrid(searchoutput_prm,width="100%",editable=True)

    #download prm list that's been edited in the window
    @render.download(filename="prm_peptide_list.csv")
    def prm_table_download():
        prm_table_view=prm_table.data_view()
        
        yield prm_table_view.to_csv(index=False)

    # #plot intensity and presence in replicates for a specified peptide
    # @render.plot(width=800,height=800)
    # def peptide_intensity():
    #     searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

    #     pickedpeptide=input.tracked_peptide()

    #     figsize=(8,8)
    #     find_ptms()
    #     protandpep=searchoutput[["Cond_Rep","R.Condition","R.Replicate","PG.ProteinGroups","PG.ProteinNames","PEP.StrippedSequence","EG.ModifiedPeptide","FG.Charge","PG.MS2Quantity","FG.MS2Quantity","PTMs"]]
    #     pickedpeptidedf=protandpep.loc[protandpep["PEP.StrippedSequence"]==pickedpeptide]
    #     peptideptms=pickedpeptidedf["PTMs"].drop_duplicates().reset_index(drop=True).tolist()
    #     peptidecharges=pickedpeptidedf["FG.Charge"].drop_duplicates().reset_index(drop=True).tolist()
    #     nummods=[]
    #     for i in pickedpeptidedf["EG.ModifiedPeptide"].tolist():
    #         nummods.append(i.count("["))
    #     pickedpeptidedf.insert(loc=len(pickedpeptidedf.columns),column="# Mods",value=nummods)
    #     peptidelist=pickedpeptidedf["EG.ModifiedPeptide"].tolist()
    #     ptmpos=[]
    #     for i in range(len(peptidelist)):
    #         modnums=pickedpeptidedf["# Mods"].tolist()[i]
    #         if modnums==0:
    #             ptmpos.append("X")
    #         elif modnums==1:
    #             ptmpos.append(peptidelist[i].find("[")-1)
    #         elif modnums>1:
    #             multimod=[x-1 for x, ele in enumerate(peptidelist[i]) if ele=="["]
    #             multimod=",".join(str(x) for x in multimod)
    #             ptmpos.append(multimod)
    #     pickedpeptidedf.insert(loc=len(pickedpeptidedf.columns),column="PTM Position",value=ptmpos)
    #     ptmpositions=pickedpeptidedf["PTM Position"].drop_duplicates().tolist()

    #     nrows=max(nummods)+1
    #     fig,ax=plt.subplots(nrows=nrows,ncols=1,figsize=figsize,sharex=True)
    #     for i in range(nrows):
    #         for j in peptidecharges:
    #             modchargegroup=pickedpeptidedf.groupby(["# Mods"]).get_group(i).groupby(["FG.Charge"]).get_group(j)
    #             #if the groups of modifications aren't all for the same mod position, split those up
    #             if len(set(modchargegroup["PTM Position"].tolist()))==1:
    #                 label=str(modchargegroup["FG.Charge"].tolist()[0])+"+"
    #                 ax[i].scatter(x=modchargegroup["Cond_Rep"],y=modchargegroup["FG.MS2Quantity"],label=label)
    #                 ax[i].set_title(modchargegroup["EG.ModifiedPeptide"].tolist()[0].strip("_"))
    #                 ax[i].set_ylabel("FG.MS2Quantity")
                    
    #                 x=np.arange(0,len(modchargegroup["Cond_Rep"]),1)
    #                 y=modchargegroup["FG.MS2Quantity"]
    #                 fit=np.poly1d(np.polyfit(x,y,1))
    #                 ax[i].plot(x,fit(x),linestyle=":")
    #             else:
    #                 multimods=modchargegroup["PTM Position"].drop_duplicates().tolist()
    #                 for k in range(len(multimods)):
    #                     multimodgroup=modchargegroup.groupby(["PTM Position"]).get_group(multimods[k])
    #                     multimodlabel=str(multimodgroup["FG.Charge"].tolist()[0])+"+, "+str(multimodgroup["PTMs"].tolist()[0])+"@"+str(multimodgroup["PTM Position"].tolist()[0])
    #                     ax[i].scatter(x=multimodgroup["Cond_Rep"],y=multimodgroup["FG.MS2Quantity"],label=multimodlabel)
    #                     ax[i].set_title(modchargegroup["PEP.StrippedSequence"].tolist()[0])
    #                     ax[i].set_ylabel("FG.MS2Quantity")
                        
    #                     x=np.arange(0,len(multimodgroup["Cond_Rep"]))
    #                     y=multimodgroup["FG.MS2Quantity"]
    #                     fit=np.poly1d(np.polyfit(x,y,1))
    #                     ax[i].plot(x,fit(x),linestyle=":")
                        
    #         ax[i].set_xticks(modchargegroup["Cond_Rep"],labels=modchargegroup["Cond_Rep"],rotation=45)
    #         ax[i].legend(loc="center left",bbox_to_anchor=(1, 0.5))
    #         fig.tight_layout()

    #     return fig
    
    # @render.plot(width=900,height=800)
    # def peptide_replicates():
    #     searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

    #     pickedpeptide=input.tracked_peptide()

    #     figsize=(8,8)
    #     find_ptms()
    #     protandpep=searchoutput[["Cond_Rep","R.Condition","R.Replicate","PG.ProteinGroups","PG.ProteinNames","PEP.StrippedSequence","EG.ModifiedPeptide","FG.Charge","PG.MS2Quantity","FG.MS2Quantity","PTMs"]]
    #     pickedpeptidedf=protandpep.loc[protandpep["PEP.StrippedSequence"]==pickedpeptide]
    #     peptideptms=pickedpeptidedf["PTMs"].drop_duplicates().reset_index(drop=True).tolist()
    #     peptidecharges=pickedpeptidedf["FG.Charge"].drop_duplicates().reset_index(drop=True).tolist()
    #     nummods=[]
    #     for i in pickedpeptidedf["EG.ModifiedPeptide"].tolist():
    #         nummods.append(i.count("["))
    #     pickedpeptidedf.insert(loc=len(pickedpeptidedf.columns),column="# Mods",value=nummods)
    #     peptidelist=pickedpeptidedf["EG.ModifiedPeptide"].tolist()
    #     ptmpos=[]
    #     for i in range(len(peptidelist)):
    #         modnums=pickedpeptidedf["# Mods"].tolist()[i]
    #         if modnums==0:
    #             ptmpos.append("X")
    #         elif modnums==1:
    #             ptmpos.append(peptidelist[i].find("[")-1)
    #         elif modnums>1:
    #             multimod=[x-1 for x, ele in enumerate(peptidelist[i]) if ele=="["]
    #             multimod=",".join(str(x) for x in multimod)
    #             ptmpos.append(multimod)
    #     pickedpeptidedf.insert(loc=len(pickedpeptidedf.columns),column="PTM Position",value=ptmpos)
    #     ptmpositions=pickedpeptidedf["PTM Position"].drop_duplicates().tolist()

    #     nrows=max(nummods)+1
    #     x=np.arange(len(sampleconditions))
    #     width=0.2
    #     fig,ax=plt.subplots(nrows=nrows,ncols=1,figsize=figsize,sharex=True)
    #     #group by # of mods, then by charge
    #     for i in range(nrows):
    #         for j in range(len(peptidecharges)):
    #             modchargegroup=pickedpeptidedf.groupby(["# Mods"]).get_group(i).groupby(["FG.Charge"]).get_group(peptidecharges[j])
    #             #if the groups of modifications aren't all for the same mod position, split those up
    #             if len(set(modchargegroup["PTM Position"].tolist()))==1:
    #                 label=str(modchargegroup["FG.Charge"].tolist()[0])+"+"
    #                 detectedinreps=modchargegroup.groupby(["R.Condition"]).size().tolist()
    #                 ax[i].bar(x+j*width,detectedinreps,label=label,width=width)
    #                 ax[i].set_title(modchargegroup["EG.ModifiedPeptide"].tolist()[0].strip("_"))
    #                 ax[i].set_ylabel("Detected in X Replicates")
    #                 ax[i].set_yticks(np.arange(0,max(repspercondition)+1,1))
    #                 ax[i].set_xticks(x+width/2,sampleconditions)
    #             else:
    #                 multimods=modchargegroup["PTM Position"].drop_duplicates().tolist()
    #                 for k in range(len(multimods)):
    #                     multimodgroup=modchargegroup.groupby(["PTM Position"]).get_group(multimods[k])
    #                     multimodlabel=str(multimodgroup["FG.Charge"].tolist()[0])+"+, "+str(multimodgroup["PTMs"].tolist()[0])+"@"+str(multimodgroup["PTM Position"].tolist()[0])
    #                     detectedinreps=multimodgroup.groupby(["R.Condition"]).size().tolist()
    #                     ax[i].bar(x+((j+2*k)*width),detectedinreps,label=multimodlabel,width=width)
    #                     ax[i].set_title(modchargegroup["PEP.StrippedSequence"].tolist()[0])
    #                     ax[i].set_ylabel("Detected in X Replicates")
    #                     ax[i].set_yticks(np.arange(0,max(repspercondition)+1,1))
    #         ax[i].legend(loc="center left",bbox_to_anchor=(1, 0.5))
    #     fig.tight_layout()

    #     return fig

#endregion

# ============================================================================= Raw Data
#region

    #take text input for data paths and make dictionaries of frame data
    @reactive.calc
    def rawfile_list():
        filelist=list(input.rawfile_input().split("\n"))
        MSframedict=dict()
        precursordict=dict()
        samplenames=[]
        for run in filelist:
            frames=pd.DataFrame(atb.read_bruker_sql(run)[2])
            MSframedict[run]=frames[frames["MsMsType"]==0].reset_index(drop=True)
            precursordict[run]=pd.DataFrame(atb.read_bruker_sql(run)[3])
            samplenames.append(run.split("\\")[-1])
        return MSframedict,precursordict,samplenames        

    #render ui for checkboxes to plot specific runs
    @render.ui
    def rawfile_checkboxes_tic():
        MSframedict,precursordict,samplenames=rawfile_list()
        opts=dict()
        keys=input.rawfile_input().split("\n")
        labels=samplenames
        for x,y in zip(keys,labels):
            opts[x]=y
        return ui.input_checkbox_group("rawfile_pick_tic","Pick files to plot data for:",choices=opts,width="800px")
    #plot TIC from raw data
    @reactive.effect
    def _():
        @render.plot(width=input.tic_width(),height=input.tic_height())
        def TIC_plot():
            MSframedict,precursordict,samplenames=rawfile_list()
            checkgroup=input.rawfile_pick_tic()
            colors=list(mcolors.TABLEAU_COLORS)
            if input.stacked_tic()==True:
                fig,ax=plt.subplots(nrows=len(checkgroup),sharex=True)
                for i,run in enumerate(checkgroup):
                    x=MSframedict[run]["Time"]/60
                    y=MSframedict[run]["SummedIntensities"]
                    ax[i].plot(x,y,label=run.split("\\")[-1],linewidth=1.5,color=colors[i])
                    ax[i].set_ylabel("Intensity")
                    ax[i].set_axisbelow(True)
                    ax[i].grid(linestyle="--")
                    legend=ax[i].legend(loc="upper left")
                    for z in legend.legend_handles:
                        z.set_linewidth(5)
            else:
                fig,ax=plt.subplots()
                for run in checkgroup:
                    x=MSframedict[run]["Time"]/60
                    y=MSframedict[run]["SummedIntensities"]
                    ax.plot(x,y,label=run.split("\\")[-1],linewidth=0.75)
                ax.set_xlabel("Time (min)")
                ax.set_ylabel("Intensity")
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                #legend=ax.legend(loc='center left', bbox_to_anchor=(1,0.5),prop={'size':10})
                legend=ax.legend(loc="upper left")
                for z in legend.legend_handles:
                    z.set_linewidth(5)
        
    #render ui for checkboxes to plot specific runs
    @render.ui
    def rawfile_checkboxes_bpc():
        MSframedict,precursordict,samplenames=rawfile_list()
        opts=dict()
        keys=input.rawfile_input().split("\n")
        labels=samplenames
        for x,y in zip(keys,labels):
            opts[x]=y
        return ui.input_checkbox_group("rawfile_pick_bpc","Pick files to plot data for:",choices=opts,width="800px")
    #plot BPC from raw data
    @reactive.effect
    def _():
        @render.plot(width=input.bpc_width(),height=input.bpc_height())
        def BPC_plot():
            MSframedict,precursordict,samplenames=rawfile_list()
            checkgroup=input.rawfile_pick_bpc()
            colors=list(mcolors.TABLEAU_COLORS)
            if input.stacked_bpc()==True:
                fig,ax=plt.subplots(nrows=len(checkgroup),sharex=True)
                for i,run in enumerate(checkgroup):
                    x=MSframedict[run]["Time"]/60
                    y=MSframedict[run]["MaxIntensity"]
                    ax[i].plot(x,y,label=run.split("\\")[-1],linewidth=1.5,color=colors[i])
                    ax[i].set_ylabel("Intensity")
                    ax[i].set_axisbelow(True)
                    ax[i].grid(linestyle="--")
                    legend=ax[i].legend(loc="upper left")
                    for z in legend.legend_handles:
                        z.set_linewidth(5)
            else:
                fig,ax=plt.subplots()
                for run in checkgroup:
                    x=MSframedict[run]["Time"]/60
                    y=MSframedict[run]["MaxIntensity"]
                    ax.plot(x,y,label=run.split("\\")[-1],linewidth=0.75)
                ax.set_xlabel("Time (min)")
                ax.set_ylabel("Intensity")
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                #legend=ax.legend(loc='center left', bbox_to_anchor=(1,0.5),prop={'size':10})
                legend=ax.legend(loc='upper left')
                for z in legend.legend_handles:
                    z.set_linewidth(5)      

    #render ui for checkboxes to plot specific runs
    @render.ui
    def rawfile_checkboxes_accutime():
        MSframedict,precursordict,samplenames=rawfile_list()
        opts=dict()
        keys=input.rawfile_input().split("\n")
        labels=samplenames
        for x,y in zip(keys,labels):
            opts[x]=y
        return ui.input_checkbox_group("rawfile_pick_accutime","Pick files to plot data for:",choices=opts,width="800px")
    #plot accumulation time from raw data
    @reactive.effect
    def _():
        @render.plot(width=input.accutime_width(),height=input.accutime_height())
        def accutime_plot():
            MSframedict,precursordict,samplenames=rawfile_list()
            checkgroup=input.rawfile_pick_accutime()
            colors=list(mcolors.TABLEAU_COLORS)
            if input.stacked_accutime()==True:
                fig,ax=plt.subplots(nrows=len(checkgroup),sharex=True)
                for i,run in enumerate(checkgroup):
                    x=MSframedict[run]["Time"]/60
                    y=MSframedict[run]["AccumulationTime"]
                    ax[i].plot(x,y,label=run.split("\\")[-1],linewidth=1.5,color=colors[i])
                    ax[i].set_ylabel("Accumulation Time (ms)")
                    ax[i].set_axisbelow(True)
                    ax[i].grid(linestyle="--")
                    legend=ax[i].legend(loc="upper left")
                    for z in legend.legend_handles:
                        z.set_linewidth(5)
            else:
                fig,ax=plt.subplots()
                for run in checkgroup:
                    x=MSframedict[run]["Time"]/60
                    y=MSframedict[run]["AccumulationTime"]
                    ax.plot(x,y,label=run.split("\\")[-1],linewidth=0.75)
                ax.set_xlabel("Time (min)")
                ax.set_ylabel("Accumulation Time (ms)")
                ax.set_axisbelow(True)
                ax.grid(linestyle="--")
                legend=ax.legend(loc='center left', bbox_to_anchor=(1,0.5),prop={'size':10})
                for z in legend.legend_handles:
                    z.set_linewidth(5)

    @render.ui
    def rawfile_buttons():
        MSframedict,precursordict,samplenames=rawfile_list()
        opts=dict()
        keys=input.rawfile_input().split("\n")
        labels=samplenames
        for x,y in zip(keys,labels):
            opts[x]=y
        return ui.input_radio_buttons("rawfile_pick","Pick file to plot data for:",choices=opts,width="800px")
    
    #input for mobility add-on for EICs
    @render.ui
    def mobility_input():
        if input.include_mobility()==True:
            return ui.input_text("mobility_input_value","Input mobility for EIC:"),ui.input_text("mobility_input_window","Input mobility window (1/k0) for EIC:")
        
    @reactive.calc
    @reactive.event(input.load_eic)
    def eic_setup():
        mz=float(input.eic_mz_input())
        ppm_error=float(input.eic_ppm_input())
        rawfile=atb.TimsTOF(input.rawfile_pick())

        low_mz=mz/(1+ppm_error/10**6)
        high_mz=mz*(1+ppm_error/10**6)

        if input.include_mobility()==True:
            mobility=float(input.mobility_input_value())
            window=float(input.mobility_input_window())
            low_mobility=mobility-window
            high_mobility=mobility+window
            eic_df=rawfile[:,low_mobility: high_mobility,0,low_mz: high_mz]
        else:
            eic_df=rawfile[:,:,0,low_mz: high_mz]

        return eic_df

    @reactive.effect
    def _():
        @render.plot(width=input.eic_width(),height=input.eic_height())
        def eic():
            eic_df=eic_setup()
            fig,ax=plt.subplots(figsize=(10,5))
            ax.plot(eic_df["rt_values_min"],eic_df["intensity_values"],linewidth=0.5)
            ax.set_xlabel("Time (min)")
            ax.set_ylabel("Intensity")
            if input.include_mobility()==True:
                ax.set_title(input.rawfile_pick().split("\\")[-1]+"\n"+"EIC: "+str(input.eic_mz_input())+", Mobility: "+str(input.mobility_input_value()))
            else:
                ax.set_title(input.rawfile_pick().split("\\")[-1]+"\n"+"EIC: "+str(input.eic_mz_input()))

#endregion

# ============================================================================= Export Tables 
#region 
    #download table of peptide IDs
    @render.download(filename=lambda: f"Peptide List_{input.searchreport()[0]['name']}.csv")
    def peptidelist():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        peptidetable=searchoutput[["PG.Genes","PG.ProteinAccessions","PG.ProteinGroups","PG.ProteinNames","EG.ModifiedPeptide"]].drop_duplicates().reset_index(drop=True)
        with io.BytesIO() as buf:
            peptidetable.to_csv(buf)
            yield buf.getvalue()

    #download table of protein ID metrics/CVs
    @render.download(filename=lambda: f"Protein CV Table_{input.searchreport()[0]['name']}.csv")
    def proteinidmetrics_download():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        cvproteingroup=searchoutput[["R.Condition","R.Replicate","PG.ProteinGroups","PG.MS2Quantity"]].drop_duplicates().reset_index(drop=True)
        cvproteinmean=cvproteingroup.drop(columns="R.Replicate").groupby(["R.Condition","PG.ProteinGroups"]).mean().rename(columns={"PG.MS2Quantity":"Mean"})
        cvproteinstdev=cvproteingroup.drop(columns="R.Replicate").groupby(["R.Condition","PG.ProteinGroups"]).std().rename(columns={"PG.MS2Quantity":"Stdev"})
        cvproteincount=cvproteingroup.drop(columns="R.Replicate").groupby(["R.Condition","PG.ProteinGroups"]).size().reset_index(drop=True)
        cvproteintable=pd.concat([cvproteinmean,cvproteinstdev],axis=1).reindex(cvproteinmean.index)
        cvproteintable["CV"]=cvproteintable["Stdev"]/cvproteintable["Mean"]*100
        cvproteintable["# replicates observed"]=cvproteincount.tolist()
        with io.BytesIO() as buf:
            cvproteintable.to_csv(buf)
            yield buf.getvalue()
    
    #download table of precursor ID metrics/CVs
    @render.download(filename=lambda: f"Precursor CV Table_{input.searchreport()[0]['name']}.csv")
    def precursoridmetrics_download():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        cvprecursorgroup=searchoutput[["R.Condition","R.Replicate","EG.ModifiedPeptide","FG.Charge","FG.MS2Quantity"]].drop_duplicates().reset_index(drop=True)

        cvprecursormean=cvprecursorgroup.drop(columns="R.Replicate").groupby(["R.Condition","EG.ModifiedPeptide","FG.Charge"]).mean().rename(columns={"FG.MS2Quantity":"Mean"})
        cvprecursorstdev=cvprecursorgroup.drop(columns="R.Replicate").groupby(["R.Condition","EG.ModifiedPeptide","FG.Charge"]).std().rename(columns={"FG.MS2Quantity":"Stdev"})
        cvprecursorcount=cvprecursorgroup.drop(columns="R.Replicate").groupby(["R.Condition","EG.ModifiedPeptide","FG.Charge"]).size().reset_index(drop=True)
        cvprecursortable=pd.concat([cvprecursormean,cvprecursorstdev],axis=1).reindex(cvprecursormean.index)
        cvprecursortable["CV"]=cvprecursortable["Stdev"]/cvprecursortable["Mean"]*100
        cvprecursortable["# replicates observed"]=cvprecursorcount.tolist()
        with io.BytesIO() as buf:
            cvprecursortable.to_csv(buf)
            yield buf.getvalue()
    
    #download table of MOMA precursors for a specified run
    @render.download(filename=lambda: f"MOMA Table_{input.searchreport()[0]['name']}.csv")
    def moma_download():
        #RT tolerance in %
        rttolerance=input.rttolerance()
        #MZ tolerance in m/z
        mztolerance=input.mztolerance()

        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()

        sample=input.cond_rep()

        columns=["EG.ModifiedPeptide","FG.Charge","EG.IonMobility","EG.ApexRT","FG.PrecMz"]
        df=searchoutput[searchoutput["Cond_Rep"].str.contains(sample)][["EG.ModifiedPeptide","FG.Charge","EG.IonMobility","EG.ApexRT","FG.PrecMz"]].sort_values(["EG.ApexRT"]).reset_index(drop=True)
        coelutingpeptides=pd.DataFrame(columns=columns)
        for i in range(len(df)):
            if i+1 not in range(len(df)):
                break
            rtpercentdiff=(abs(df["EG.ApexRT"][i]-df["EG.ApexRT"][i+1])/df["EG.ApexRT"][i])*100
            mzdiff=abs(df["FG.PrecMz"][i]-df["FG.PrecMz"][i+1])
            if rtpercentdiff <= rttolerance and mzdiff <= mztolerance:
                coelutingpeptides.loc[len(coelutingpeptides)]=df.iloc[i].tolist()
                coelutingpeptides.loc[len(coelutingpeptides)]=df.iloc[i+1].tolist()

        #adding a column for a rough group number for each group of peptides detected
        for i in range(len(coelutingpeptides)):
            if i+1 not in range(len(coelutingpeptides)):
                break
            rtpercentdiff=(abs(coelutingpeptides["EG.ApexRT"][i]-coelutingpeptides["EG.ApexRT"][i+1])/coelutingpeptides["EG.ApexRT"][i])*100
            mzdiff=abs(coelutingpeptides["FG.PrecMz"][i]-coelutingpeptides["FG.PrecMz"][i+1])
            if rtpercentdiff <= rttolerance and mzdiff <= mztolerance:
                coelutingpeptides.loc[coelutingpeptides.index[i],"Group"]=i

        with io.BytesIO() as buf:
            coelutingpeptides.to_csv(buf,index=False)
            yield buf.getvalue()

    #download table of PTMs per precursor
    @render.download(filename=lambda: f"PTM List_{input.searchreport()[0]['name']}.csv")
    def ptmlist_download():
        searchoutput,resultdf,sampleconditions,maxreplicatelist,averagedf,numconditions,repspercondition,numsamples=variables_dfs()
        ptmdf=pd.DataFrame()
        for condition in sampleconditions:
            df=searchoutput[searchoutput["R.Condition"].str.contains(condition)][["EG.ModifiedPeptide","FG.Charge"]].drop_duplicates().reset_index(drop=True)
            dfptmlist=[]
            numptms=[]
            for i in df["EG.ModifiedPeptide"]:
                foundptms=re.findall(r"[^[]*\[([^]]*)\]",i)
                dfptmlist.append(foundptms)
                numptms.append(len(foundptms))
            dfptmlist=pd.Series(dfptmlist).value_counts().to_frame().reset_index().rename(columns={"index":condition,"count":condition+"_count"})
            ptmdf=pd.concat([ptmdf,dfptmlist],axis=1)
        with io.BytesIO() as buf:
            ptmdf.to_csv(buf,index=False)
            yield buf.getvalue()

#endregion

app=App(app_ui,server)