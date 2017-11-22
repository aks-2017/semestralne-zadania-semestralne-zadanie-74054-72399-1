#!/bin/sh

#!!run script as root!!

#remove old packages
apt-get remove openvswitch-common openvswitch-datapath-dkms openvswitch-controller openvswitch-pki openvswitch-switch

#download and unpack
cd /root
wget http://openvswitch.org/releases/openvswitch-2.5.0.tar.gz
tar zxvf openvswitch-2.5.0.tar.gz

#build and install
cd openvswitch-2.5.0/
./configure --prefix=/usr --with-linux=/lib/modules/`uname -r`/build
make
make install
make modules_install
rmmod openvswitch
depmod -a

#postinstalation steps
/etc/init.d/openvswitch-controller stop
update-rc.d openvswitch-controller disable
/etc/init.d/openvswitch-switch start
