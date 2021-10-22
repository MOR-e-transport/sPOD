import matplotlib.pyplot as plt
import numpy as np
from lib.farge_colormaps import farge_colormap_multi

fc = farge_colormap_multi( etalement_du_zero=0.2, limite_faible_fort=0.5)

from matplotlib import rc
rc('font',**{'family':'serif','serif':['Helvetica'],'size'   : 12})
#
rc('text', usetex=True)

pic_dir = "../imgs"
plt.close("all")

def show_animation(q, Xgrid=None, cycles=1, frequency = 1, figure_number = None, cmap = fc, vmin = None,vmax=None, save_path=None):


    ndim = np.size(Xgrid)
    ntime = q.shape[-1]
    if figure_number == None:
        fig, ax = plt.subplots()
    else:
        fig, ax = plt.subplots(num=figure_number)

    if Xgrid is not None:

        h = ax.pcolormesh(Xgrid[0], Xgrid[1], q[..., 0], cmap = cmap)

        if vmin is None:
            vmin = np.min(q)
        if vmax is None:
            vmax = np.max(q)
        h.set_clim(vmin, vmax)
        fig.colorbar(h)
        ax.axis("image")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel(r"$x$")
        ax.set_ylabel(r"$y$")
        for t in range(0, cycles * ntime, frequency):
            h.set_array(q[:-1,:-1,t % ntime].ravel())
            if save_path is not None:
                fig.savefig(save_path+"/vid_%3.3d.png" % t)
            plt.draw()
            plt.pause(0.05)

    else:
        x = np.arange(0,np.size(q,0))
        h, = ax.plot(x,q[:, 0])
        ax.set_ylim(np.min(q),np.max(q))
        ax.set_xlabel(r"$x$")
        for t in range(0, cycles * ntime, frequency):
            h.set_data(x,q[:,t % ntime])
            if save_path is not None:
                fig.savefig(save_path+"/vid_%3.3d.png" % t)
            plt.draw()
            plt.pause(0.05)

def save_fig(filepath, figure=None, **kwargs):
    import tikzplotlib
    import os
    import matplotlib.pyplot as plt

    ## split extension
    fpath = os.path.splitext(filepath)[0]
    ## get figure handle
    if figure is None:
        figure = plt.gcf()
    figure.savefig(fpath + ".png", dpi=600, transparent=True)
    tikzplotlib.save(
        figure=figure,
        filepath=fpath + ".tex",
        axis_height='\\figureheight',
        axis_width='\\figurewidth',
        override_externals=True,
        **kwargs
    )

